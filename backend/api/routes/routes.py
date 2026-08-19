"""
LogSage AI — API Routes
POST /logs/upload, POST /logs/stream, GET /incidents, GET /clusters,
GET /metrics, GET /alerts, POST /analyze/{incident_id}, WS /live
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ai.analysis.analyzer import analyze_root_cause, generate_timeline
from core.database import get_session
from core.redis_client import (
    CHANNEL_ALERTS,
    CHANNEL_LIVE_EVENTS,
    get_pubsub,
    get_redis,
    queue_length,
)
from models.models import (
    IncidentSeverity,
    IncidentStatus,
    IncidentSummary,
    LogSource,
)
from repositories.repositories import (
    AlertRepository,
    ClusterRepository,
    IncidentRepository,
    LogRepository,
)
from schemas.schemas import (
    AlertListResponse,
    ClusterListResponse,
    DashboardData,
    IncidentListResponse,
    IncidentResponse,
    IncidentSummaryResponse,
    IncidentUpdateRequest,
    IngestionResult,
    MetricsSnapshot,
    RootCauseAnalysisResponse,
)
from services.services import IngestionService, MetricsService
from utils.log_parser import parse_log_content, parse_stream_line
from utils.sample_data import generate_sample_logs

logger = structlog.get_logger(__name__)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_session)]

MAX_UPLOAD_MB = 100


# ── WebSocket connection manager ──────────────────────────────────────────────

class WSConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("WS client connected", total=len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)
        logger.info("WS client disconnected", total=len(self.active))

    async def broadcast(self, message: str) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)


ws_manager = WSConnectionManager()


# ── Log Ingestion ─────────────────────────────────────────────────────────────

@router.post("/logs/upload", response_model=IngestionResult, status_code=201)
async def upload_logs(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
) -> IngestionResult:
    """Upload a log file (TXT, JSON, CSV). Max 100 MB."""
    if file.size and file.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_UPLOAD_MB} MB limit",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    entries, total_lines, error_lines = parse_log_content(
        raw,
        session_id=str(uuid.uuid4()),
        source=LogSource.FILE_UPLOAD,
    )

    if not entries:
        raise HTTPException(status_code=422, detail="No parseable log entries found")

    svc = IngestionService(db)
    return await svc.ingest(
        entries=entries,
        source=LogSource.FILE_UPLOAD,
        filename=file.filename,
        total_lines=total_lines,
        error_lines=error_lines,
    )


@router.post("/logs/stream", response_model=IngestionResult, status_code=201)
async def stream_logs_batch(
    payload: dict,
    db: AsyncSession = Depends(get_session),
) -> IngestionResult:
    """Ingest a batch of log lines via REST (for programmatic use)."""
    lines = payload.get("lines", [])
    if not lines:
        raise HTTPException(status_code=400, detail="No log lines provided")

    session_id = payload.get("session_id") or str(uuid.uuid4())
    entries = []
    for line in lines[:10_000]:
        entry = parse_stream_line(str(line), session_id)
        if entry:
            entries.append(entry)

    svc = IngestionService(db)
    return await svc.ingest(
        entries=entries,
        source=LogSource.API,
        total_lines=len(lines),
        error_lines=len(lines) - len(entries),
    )


@router.post("/logs/simulate", response_model=IngestionResult, status_code=201)
async def simulate_logs(
    count: int = Query(default=100, ge=10, le=5000),
    scenario: str = Query(default="mixed"),
    db: AsyncSession = Depends(get_session),
) -> IngestionResult:
    """Generate and ingest realistic simulated logs."""
    session_id = str(uuid.uuid4())
    entries = generate_sample_logs(count=count, scenario=scenario, session_id=session_id)
    svc = IngestionService(db)
    return await svc.ingest(
        entries=entries,
        source=LogSource.SIMULATED,
        total_lines=count,
        error_lines=0,
    )


# ── Incidents ─────────────────────────────────────────────────────────────────

@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    db: DB,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> IncidentListResponse:
    repo = IncidentRepository(db)
    incidents, total = await repo.list_with_filters(
        status=status, severity=severity, offset=offset, limit=limit
    )
    counts = await repo.count_by_status()
    return IncidentListResponse(
        incidents=[IncidentResponse.model_validate(i) for i in incidents],
        total=total,
        open_count=counts.get("open", 0),
        critical_count=counts.get("critical", 0),
    )


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, db: DB) -> IncidentResponse:
    repo = IncidentRepository(db)
    incident = await repo.get_with_relations(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse.model_validate(incident)


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    req: IncidentUpdateRequest,
    db: DB,
) -> IncidentResponse:
    repo = IncidentRepository(db)
    incident = await repo.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if req.status:
        incident.status = req.status
        if req.status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.utcnow()
    if req.severity:
        incident.severity = req.severity
    if req.description:
        incident.description = req.description
    await repo.update(incident)
    return IncidentResponse.model_validate(incident)


@router.post("/incidents/{incident_id}/analyze", response_model=RootCauseAnalysisResponse)
async def trigger_analysis(
    incident_id: str,
    db: DB,
    use_rag: bool = Query(default=True),
) -> RootCauseAnalysisResponse:
    """Trigger AI root cause analysis for an incident."""
    incident_repo = IncidentRepository(db)
    log_repo = LogRepository(db)

    incident = await incident_repo.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Fetch associated logs
    log_entries = await log_repo.get_by_session(
        incident.cluster_id or incident_id, limit=50
    )

    import time
    start = time.monotonic()
    analysis = await analyze_root_cause(incident, log_entries, use_rag=use_rag)

    # Persist analysis back to incident
    incident.root_causes = [rc.model_dump() for rc in analysis["root_causes"]]
    incident.recommended_fixes = analysis["recommended_fixes"]
    incident.ai_confidence = analysis["ai_confidence"]
    incident.ai_summary = analysis["ai_summary"]

    # Persist summary
    summary = IncidentSummary(
        id=str(uuid.uuid4()),
        incident_id=incident.id,
        executive_summary=analysis["executive_summary"],
        technical_details=analysis.get("technical_details"),
        impact_assessment=analysis.get("impact_assessment"),
        prevention_steps=analysis.get("prevention_steps"),
        similar_past_incidents=analysis.get("similar_incidents"),
        model_used=analysis["model_used"],
        token_usage=analysis.get("token_usage"),
    )
    db.add(summary)
    await incident_repo.update(incident)

    return RootCauseAnalysisResponse(
        incident_id=incident_id,
        root_causes=analysis["root_causes"],
        recommended_fixes=analysis["recommended_fixes"],
        ai_confidence=analysis["ai_confidence"],
        ai_summary=analysis["ai_summary"],
        timeline=analysis.get("timeline", []),
        similar_incidents=analysis.get("similar_incidents"),
        model_used=analysis["model_used"],
        analysis_time_ms=analysis["analysis_time_ms"],
    )


@router.get("/incidents/{incident_id}/summary", response_model=IncidentSummaryResponse)
async def get_incident_summary(incident_id: str, db: DB) -> IncidentSummaryResponse:
    incident_repo = IncidentRepository(db)
    incident = await incident_repo.get_with_relations(incident_id)
    if not incident or not incident.summary:
        raise HTTPException(status_code=404, detail="Summary not found — trigger analysis first")
    return IncidentSummaryResponse.model_validate(incident.summary)


# ── Clusters ──────────────────────────────────────────────────────────────────

@router.get("/clusters", response_model=ClusterListResponse)
async def list_clusters(
    db: DB,
    limit: int = Query(default=20, ge=1, le=100),
) -> ClusterListResponse:
    repo = ClusterRepository(db)
    clusters = await repo.get_top_by_count(limit=limit)
    total = await repo.count()
    return ClusterListResponse(
        clusters=clusters,
        total=total,
    )


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=MetricsSnapshot)
async def get_metrics(db: DB) -> MetricsSnapshot:
    svc = MetricsService(db)
    return await svc.get_snapshot()


@router.get("/metrics/dashboard", response_model=DashboardData)
async def get_dashboard(db: DB) -> DashboardData:
    svc = MetricsService(db)
    metrics = await svc.get_snapshot()

    incident_repo = IncidentRepository(db)
    cluster_repo = ClusterRepository(db)
    log_repo = LogRepository(db)

    recent_incidents_raw, _ = await incident_repo.list_with_filters(limit=5)
    top_clusters = await cluster_repo.get_top_by_count(limit=5)
    heatmap = await log_repo.get_error_heatmap()

    return DashboardData(
        metrics=metrics,
        recent_incidents=[IncidentResponse.model_validate(i) for i in recent_incidents_raw],
        top_clusters=top_clusters,
        error_heatmap=heatmap,
        events_timeline=[],
    )


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(db: DB, limit: int = Query(default=50, le=200)) -> AlertListResponse:
    repo = AlertRepository(db)
    alerts = await repo.get_firing(limit=limit)
    firing = await repo.count_firing()
    total = await repo.count()
    return AlertListResponse(alerts=alerts, total=total, firing_count=firing)


# ── WebSocket Live Stream ─────────────────────────────────────────────────────

@router.websocket("/live")
async def websocket_live(websocket: WebSocket) -> None:
    """
    Real-time event stream.
    Subscribes to Redis pub/sub channels and forwards to client.
    Also accepts log lines from client for live ingestion.
    """
    await ws_manager.connect(websocket)
    pubsub = await get_pubsub()
    await pubsub.subscribe(CHANNEL_LIVE_EVENTS, CHANNEL_ALERTS)

    try:
        # Send initial heartbeat
        await websocket.send_text(json.dumps({
            "type": "heartbeat",
            "payload": {"status": "connected"},
            "timestamp": datetime.utcnow().isoformat(),
        }))

        import asyncio

        async def forward_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])

        async def receive_client():
            async for data in websocket.iter_text():
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "log_line":
                        # Live log ingestion via WebSocket
                        line = msg.get("line", "")
                        if line:
                            await websocket.send_text(json.dumps({
                                "type": "ack",
                                "payload": {"line": line[:100]},
                                "timestamp": datetime.utcnow().isoformat(),
                            }))
                except Exception:
                    pass

        await asyncio.gather(forward_redis(), receive_client())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
    finally:
        await pubsub.unsubscribe(CHANNEL_LIVE_EVENTS, CHANNEL_ALERTS)
        await pubsub.close()
        ws_manager.disconnect(websocket)
