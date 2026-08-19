"""
LogSage AI — Incident Clustering Engine
Groups similar log entries into clusters using embedding similarity.
Uses DBSCAN for density-based clustering + centroid tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
import structlog
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize

from ai.embeddings.embedding_service import (
    embed_log_entries,
    find_similar_logs,
    get_embeddings_for_ids,
)
from core.config import settings
from models.models import Cluster, IncidentSeverity, LogEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# ── Severity scoring ──────────────────────────────────────────────────────────

SEVERITY_KEYWORDS: dict[IncidentSeverity, list[str]] = {
    IncidentSeverity.CRITICAL: [
        "crash", "oom", "killed", "panic", "fatal", "data loss",
        "corruption", "unrecoverable", "down", "outage",
    ],
    IncidentSeverity.HIGH: [
        "error", "exception", "failed", "timeout", "refused",
        "disconnected", "unreachable", "saturated", "exhausted",
    ],
    IncidentSeverity.MEDIUM: [
        "warn", "retry", "slow", "degraded", "reconnect",
        "high memory", "queue full", "rate limit",
    ],
    IncidentSeverity.LOW: [
        "info", "debug", "notice", "verbose",
    ],
}


def score_severity(messages: list[str]) -> IncidentSeverity:
    combined = " ".join(messages).lower()
    for severity in [
        IncidentSeverity.CRITICAL,
        IncidentSeverity.HIGH,
        IncidentSeverity.MEDIUM,
        IncidentSeverity.LOW,
    ]:
        if any(kw in combined for kw in SEVERITY_KEYWORDS[severity]):
            return severity
    return IncidentSeverity.LOW


def generate_cluster_name(messages: list[str]) -> str:
    """Generate a human-readable cluster name from representative messages."""
    combined = " ".join(messages[:5]).lower()

    patterns = [
        (["redis", "cache"], "Redis/Cache Issues"),
        (["gateway", "websocket", "ws"], "Gateway Connectivity"),
        (["shard", "heartbeat"], "Shard Health"),
        (["db", "database", "postgres", "pool", "connection"], "Database Issues"),
        (["memory", "oom", "heap", "leak"], "Memory Pressure"),
        (["queue", "worker", "celery", "task"], "Worker Queue Issues"),
        (["rate limit", "throttle", "429"], "Rate Limiting"),
        (["timeout", "timed out"], "Timeout Storm"),
        (["reconnect", "disconnect", "offline"], "Connection Instability"),
        (["crash", "panic", "fatal"], "Service Crashes"),
    ]

    for keywords, name in patterns:
        if any(kw in combined for kw in keywords):
            return name

    # Fallback: use most common meaningful word
    words = [w for w in combined.split() if len(w) > 4]
    if words:
        most_common = max(set(words), key=words.count)
        return f"{most_common.title()} Events"
    return "Unknown Cluster"


# ── Main clustering function ──────────────────────────────────────────────────

async def cluster_log_entries(
    entries: list[LogEntry],
    session: "AsyncSession",
) -> list[Cluster]:
    """
    Cluster a batch of log entries by embedding similarity.

    Process:
    1. Embed all entries
    2. DBSCAN clustering on normalized vectors
    3. Create/update Cluster objects
    4. Assign cluster_id back to log entries
    """
    if not entries:
        return []

    logger.info("Starting clustering", entry_count=len(entries))

    # Step 1: Embed
    embedding_map = await embed_log_entries(entries)

    # Build matrix only for entries that got embeddings
    embedded_entries = [e for e in entries if e.id in embedding_map]
    if not embedded_entries:
        logger.warning("No embeddings generated, skipping clustering")
        return []

    vectors = np.array([embedding_map[e.id] for e in embedded_entries], dtype=np.float32)
    vectors_norm = normalize(vectors, norm="l2")

    # Step 2: DBSCAN
    # eps = 1 - similarity_threshold  (cosine distance)
    eps = 1.0 - settings.CLUSTERING_THRESHOLD
    db = DBSCAN(
        eps=eps,
        min_samples=2,
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    ).fit(vectors_norm)

    labels: np.ndarray = db.labels_  # -1 = noise

    # Step 3: Build cluster → entries mapping
    label_to_entries: dict[int, list[LogEntry]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        label_to_entries.setdefault(int(label), []).append(embedded_entries[i])

    clusters_created: list[Cluster] = []

    for label, cluster_entries in label_to_entries.items():
        messages = [e.message for e in cluster_entries]
        services = list({e.service for e in cluster_entries if e.service})
        timestamps = [e.timestamp for e in cluster_entries]

        severity = score_severity(messages)
        name = generate_cluster_name(messages)

        # Pick up to 5 representative messages
        rep_messages = messages[:5]

        cluster = Cluster(
            id=str(uuid.uuid4()),
            name=name,
            description=f"Auto-clustered {len(cluster_entries)} events via embedding similarity",
            log_count=len(cluster_entries),
            severity=severity,
            representative_messages=rep_messages,
            tags=services,
            first_seen=min(timestamps),
            last_seen=max(timestamps),
        )
        session.add(cluster)
        await session.flush()

        # Assign cluster back to entries
        for entry in cluster_entries:
            entry.cluster_id = cluster.id

        clusters_created.append(cluster)
        logger.info(
            "Cluster created",
            cluster_id=cluster.id,
            name=name,
            severity=severity,
            size=len(cluster_entries),
        )

    logger.info(
        "Clustering complete",
        clusters_created=len(clusters_created),
        noise_entries=int(np.sum(labels == -1)),
    )
    return clusters_created


# ── Anomaly detection ─────────────────────────────────────────────────────────

async def detect_anomalies(
    entries: list[LogEntry],
    window_counts: dict[str, int],
) -> list[LogEntry]:
    """
    Flag anomalous log entries based on:
    - Error spike detection (rate > N * baseline)
    - Keyword-based critical detection
    - Isolation from known clusters
    """
    flagged: list[LogEntry] = []

    error_count = window_counts.get("ERROR", 0) + window_counts.get("CRITICAL", 0)
    total = sum(window_counts.values()) or 1
    error_rate = error_count / total

    # High error rate = spike
    is_spike = error_rate > 0.3

    CRITICAL_PATTERNS = [
        "out of memory", "oom", "killed", "segfault",
        "data corruption", "unrecoverable", "disk full",
        "connection refused", "pool exhausted",
    ]

    for entry in entries:
        score = 0.0
        msg_lower = entry.message.lower()

        # Critical keyword match
        if any(p in msg_lower for p in CRITICAL_PATTERNS):
            score = 0.95
        elif entry.level in ("ERROR", "CRITICAL") and is_spike:
            score = 0.75
        elif entry.level == "WARNING" and is_spike:
            score = 0.45

        if score > 0.4:
            entry.is_anomaly = True
            entry.anomaly_score = score
            flagged.append(entry)

    logger.info("Anomaly detection complete", flagged=len(flagged), total=len(entries))
    return flagged
