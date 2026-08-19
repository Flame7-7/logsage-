"""
LogSage AI — Service Layer
Orchestrates ingestion, incident detection, alert triggering, and metrics.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from ai.clustering import cluster_log_entries, detect_anomalies
from ai.embeddings.embedding_service import embed_log_entries
from core.config import settings
from core.redis_client import (
    CHANNEL_ALERTS,
    CHANNEL_LIVE_EVENTS,
    get_counter,
    increment_counter,
    publish,
    queue_length,
)
from models.models import (
    Alert,
    AlertStatus,
    Cluster,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IngestionSession,
    LogSource,
)
from repositories.repositories import (
    AlertRepository,
    ClusterRepository,
    IncidentRepository,
    IngestionSessionRepository,
    LogRepository,
)
from schemas.schemas import IngestionResult, MetricsSnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# ── Ingestion Service ─────────────────────────────────────────────────────────

class IngestionService:
    def __init__(self, session: "AsyncSession") -> None:
        self.session = session
        self.log_repo = LogRepository(session)
        self.cluster_repo = ClusterRepository(session)
        self.incident_repo = IncidentRepository(session)
        self.session_repo = IngestionSessionRepository(session)

    async def ingest(
        self,
        entries: list,
        source: LogSource,
        filename: str | None = None,
        total_lines: int = 0,
        error_lines: int = 0,
    ) -> IngestionResult:
        start = time.monotonic()
        session_id = str(uuid.uuid4())

        # Create ingestion session record
        ing_session = IngestionSession(
            id=session_id,
            source=source,
            filename=filename,
            total_lines=total_lines,
            processed_lines=len(entries),
            error_lines=error_lines,
            status="processing",
            started_at=datetime.utcnow(),
        )
        self.session.add(ing_session)
        await self.session.flush()

        # Persist log entries
        await self.log_repo.bulk_create(entries)

        # Get window counts for anomaly detection
        window_counts = await self.log_repo.count_by_level_in_window(
            settings.ANOMALY_WINDOW_SECONDS
        )

        # Anomaly detection
        anomalies = await detect_anomalies(entries, window_counts)

        # Clustering
        clusters = await cluster_log_entries(entries, self.session)

        # Incident detection from clusters
        incidents = await self._detect_incidents(clusters, entries)

        # Alert evaluation
        await self._evaluate_alerts(window_counts, entries)

        # Update ingestion session
        ing_session.status = "completed"
        ing_session.completed_at = datetime.utcnow()

        # Publish live events to Redis
        await self._publish_live_events(entries[:10], incidents)

        # Track metrics
        await increment_counter("logsage:metrics:total_logs", len(entries))
        await increment_counter("logsage:metrics:total_incidents", len(incidents))

        elapsed_ms = (time.monotonic() - start) * 1000

        result = IngestionResult(
            session_id=session_id,
            total_lines=total_lines,
            processed_lines=len(entries),
            error_lines=error_lines,
            incidents_detected=len(incidents),
            clusters_updated=len(clusters),
            processing_time_ms=round(elapsed_ms, 2),
        )

        logger.info(
            "Ingestion complete",
            session_id=session_id,
            logs=len(entries),
            clusters=len(clusters),
            incidents=len(incidents),
            anomalies=len(anomalies),
            elapsed_ms=round(elapsed_ms, 2),
        )
        return result

    async def _detect_incidents(
        self,
        clusters: list[Cluster],
        entries: list,
    ) -> list[Incident]:
        incidents = []
        for cluster in clusters:
            if cluster.severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
                services = list(set(
                    e.service for e in entries
                    if e.cluster_id == cluster.id and e.service
                ))
                incident = Incident(
                    id=str(uuid.uuid4()),
                    title=f"{cluster.name} — {cluster.severity.upper()} Incident",
                    description=cluster.description,
                    severity=cluster.severity,
                    status=IncidentStatus.OPEN,
                    cluster_id=cluster.id,
                    affected_services=services or None,
                    log_count=cluster.log_count,
                    detected_at=cluster.first_seen,
                )
                self.session.add(incident)
                incidents.append(incident)

        if incidents:
            await self.session.flush()
        return incidents

    async def _evaluate_alerts(
        self,
        window_counts: dict[str, int],
        entries: list,
    ) -> None:
        """Check thresholds and fire alerts."""
        error_count = window_counts.get("ERROR", 0) + window_counts.get("CRITICAL", 0)
        alert_repo = AlertRepository(self.session)

        # Redis failure alert
        redis_failures = sum(
            1 for e in entries
            if e.service and "redis" in e.service.lower()
            and str(e.level) in ("ERROR", "CRITICAL")
        )
        if redis_failures >= settings.ALERT_REDIS_FAILURE_THRESHOLD:
            await self._fire_alert(
                alert_type="redis_failure_threshold",
                title="Redis Failure Threshold Exceeded",
                message=f"Detected {redis_failures} Redis failures in current batch",
                severity=IncidentSeverity.HIGH,
                threshold=settings.ALERT_REDIS_FAILURE_THRESHOLD,
                actual=redis_failures,
            )

        # Reconnect storm alert
        reconnects = sum(
            1 for e in entries
            if "reconnect" in e.message.lower() or "disconnect" in e.message.lower()
        )
        if reconnects >= settings.ALERT_RECONNECT_STORM_THRESHOLD:
            await self._fire_alert(
                alert_type="reconnect_storm",
                title="Reconnect Storm Detected",
                message=f"Detected {reconnects} reconnect events",
                severity=IncidentSeverity.HIGH,
                threshold=settings.ALERT_RECONNECT_STORM_THRESHOLD,
                actual=reconnects,
            )

        # Queue size alert
        q_size = await queue_length("logsage:queue:ingestion")
        if q_size >= settings.ALERT_QUEUE_SIZE_THRESHOLD:
            await self._fire_alert(
                alert_type="queue_saturation",
                title="Ingestion Queue Saturation",
                message=f"Queue size {q_size} exceeds threshold {settings.ALERT_QUEUE_SIZE_THRESHOLD}",
                severity=IncidentSeverity.MEDIUM,
                threshold=settings.ALERT_QUEUE_SIZE_THRESHOLD,
                actual=q_size,
            )

    async def _fire_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        severity: IncidentSeverity,
        threshold: float,
        actual: float,
    ) -> None:
        alert = Alert(
            id=str(uuid.uuid4()),
            alert_type=alert_type,
            title=title,
            message=message,
            severity=severity,
            status=AlertStatus.FIRING,
            threshold_value=threshold,
            actual_value=actual,
            fired_at=datetime.utcnow(),
        )
        self.session.add(alert)
        await self.session.flush()

        # Publish alert to Redis channel
        import json
        await publish(
            CHANNEL_ALERTS,
            json.dumps({
                "type": "alert",
                "alert_type": alert_type,
                "title": title,
                "severity": str(severity),
                "timestamp": datetime.utcnow().isoformat(),
            }),
        )
        logger.warning("Alert fired", type=alert_type, title=title, actual=actual)

    async def _publish_live_events(
        self,
        entries: list,
        incidents: list[Incident],
    ) -> None:
        import json
        for entry in entries:
            payload = {
                "type": "log_entry",
                "payload": {
                    "id": entry.id,
                    "timestamp": entry.timestamp.isoformat(),
                    "level": str(entry.level),
                    "service": entry.service,
                    "message": entry.message[:200],
                    "is_anomaly": entry.is_anomaly,
                },
            }
            await publish(CHANNEL_LIVE_EVENTS, json.dumps(payload))

        for incident in incidents:
            payload = {
                "type": "incident",
                "payload": {
                    "id": incident.id,
                    "title": incident.title,
                    "severity": str(incident.severity),
                    "detected_at": incident.detected_at.isoformat(),
                },
            }
            await publish(CHANNEL_LIVE_EVENTS, json.dumps(payload))


# ── Metrics Service ───────────────────────────────────────────────────────────

class MetricsService:
    def __init__(self, session: "AsyncSession") -> None:
        self.session = session
        self.log_repo = LogRepository(session)
        self.incident_repo = IncidentRepository(session)
        self.alert_repo = AlertRepository(session)
        self.cluster_repo = ClusterRepository(session)

    async def get_snapshot(self) -> MetricsSnapshot:
        events_per_sec = await self.log_repo.get_events_per_second()
        incident_counts = await self.incident_repo.count_by_status()
        total_incidents = sum(incident_counts.values())
        open_incidents = incident_counts.get("open", 0)
        critical_incidents = incident_counts.get("critical", 0)
        cluster_count = await self.cluster_repo.count()
        total_logs = await self.log_repo.count()
        firing_alerts = await self.alert_repo.count_firing()
        q_size = await queue_length("logsage:queue:ingestion")

        window_counts = await self.log_repo.count_by_level_in_window(300)
        total_window = sum(window_counts.values()) or 1
        error_rate = (
            window_counts.get("ERROR", 0) + window_counts.get("CRITICAL", 0)
        ) / total_window

        return MetricsSnapshot(
            timestamp=datetime.utcnow(),
            events_per_second=round(events_per_sec, 2),
            incident_count=total_incidents,
            open_incident_count=open_incidents,
            critical_incident_count=critical_incidents,
            cluster_count=cluster_count,
            total_log_count=total_logs,
            error_rate=round(error_rate, 4),
            queue_size=q_size,
            processing_latency_ms=0.0,  # Updated by Prometheus
            anomaly_count=0,
        )
