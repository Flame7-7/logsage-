"""
LogSage AI — Pydantic v2 Schemas
Request/response models with full validation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.models import AlertStatus, IncidentSeverity, IncidentStatus, LogLevel, LogSource


# ── Base ──────────────────────────────────────────────────────────────────────

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── Log Entry Schemas ─────────────────────────────────────────────────────────

class LogEntryCreate(BaseSchema):
    session_id: str
    timestamp: datetime
    level: LogLevel
    source: LogSource
    service: str | None = None
    message: str = Field(..., min_length=1, max_length=10_000)
    raw_line: str | None = None
    extra_fields: dict[str, Any] | None = None


class LogEntryResponse(BaseSchema):
    id: str
    session_id: str
    timestamp: datetime
    level: LogLevel
    source: LogSource
    service: str | None
    message: str
    is_anomaly: bool
    anomaly_score: float | None
    cluster_id: str | None
    incident_id: str | None
    created_at: datetime


class LogStreamEntry(BaseSchema):
    """Single log line from WebSocket stream."""
    timestamp: datetime | None = None
    level: str = "INFO"
    service: str | None = None
    message: str

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, v: str) -> str:
        return v.upper()


# ── Ingestion Schemas ─────────────────────────────────────────────────────────

class IngestionSessionResponse(BaseSchema):
    id: str
    source: LogSource
    filename: str | None
    total_lines: int
    processed_lines: int
    error_lines: int
    status: str
    started_at: datetime
    completed_at: datetime | None


class IngestionResult(BaseSchema):
    session_id: str
    total_lines: int
    processed_lines: int
    error_lines: int
    incidents_detected: int
    clusters_updated: int
    processing_time_ms: float


# ── Cluster Schemas ───────────────────────────────────────────────────────────

class ClusterResponse(BaseSchema):
    id: str
    name: str
    description: str | None
    log_count: int
    severity: IncidentSeverity
    representative_messages: list[str] | None
    tags: list[str] | None
    first_seen: datetime
    last_seen: datetime
    created_at: datetime


class ClusterListResponse(BaseSchema):
    clusters: list[ClusterResponse]
    total: int


# ── Incident Schemas ──────────────────────────────────────────────────────────

class RootCause(BaseSchema):
    cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: str | None = None


class TimelineEvent(BaseSchema):
    timestamp: datetime
    event: str
    level: str | None = None
    service: str | None = None


class IncidentCreate(BaseSchema):
    title: str
    description: str | None = None
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    cluster_id: str | None = None
    detected_at: datetime


class IncidentResponse(BaseSchema):
    id: str
    title: str
    description: str | None
    severity: IncidentSeverity
    status: IncidentStatus
    cluster_id: str | None
    root_causes: list[RootCause] | None
    recommended_fixes: list[str] | None
    timeline: list[TimelineEvent] | None
    ai_confidence: float | None
    ai_summary: str | None
    affected_services: list[str] | None
    log_count: int
    detected_at: datetime
    resolved_at: datetime | None
    created_at: datetime


class IncidentListResponse(BaseSchema):
    incidents: list[IncidentResponse]
    total: int
    open_count: int
    critical_count: int


class IncidentUpdateRequest(BaseSchema):
    status: IncidentStatus | None = None
    severity: IncidentSeverity | None = None
    description: str | None = None


# ── Alert Schemas ─────────────────────────────────────────────────────────────

class AlertResponse(BaseSchema):
    id: str
    incident_id: str | None
    alert_type: str
    title: str
    message: str
    severity: IncidentSeverity
    status: AlertStatus
    threshold_value: float | None
    actual_value: float | None
    fired_at: datetime
    resolved_at: datetime | None


class AlertListResponse(BaseSchema):
    alerts: list[AlertResponse]
    total: int
    firing_count: int


# ── Summary Schemas ───────────────────────────────────────────────────────────

class IncidentSummaryResponse(BaseSchema):
    id: str
    incident_id: str
    executive_summary: str
    technical_details: str | None
    impact_assessment: str | None
    prevention_steps: list[str] | None
    similar_past_incidents: list[dict] | None
    model_used: str
    generated_at: datetime


# ── Metrics Schemas ───────────────────────────────────────────────────────────

class MetricsSnapshot(BaseSchema):
    timestamp: datetime
    events_per_second: float
    incident_count: int
    open_incident_count: int
    critical_incident_count: int
    cluster_count: int
    total_log_count: int
    error_rate: float
    queue_size: int
    processing_latency_ms: float
    anomaly_count: int


class ErrorHeatmapPoint(BaseSchema):
    hour: int  # 0-23
    day: int   # 0-6 (Mon-Sun)
    count: int
    severity: str


class LatencyDataPoint(BaseSchema):
    timestamp: datetime
    p50_ms: float
    p95_ms: float
    p99_ms: float


class DashboardData(BaseSchema):
    metrics: MetricsSnapshot
    recent_incidents: list[IncidentResponse]
    top_clusters: list[ClusterResponse]
    error_heatmap: list[ErrorHeatmapPoint]
    events_timeline: list[dict]


# ── WebSocket Schemas ─────────────────────────────────────────────────────────

class WSMessage(BaseSchema):
    type: str  # "log_entry" | "incident" | "alert" | "metrics" | "heartbeat"
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSLogStream(BaseSchema):
    lines: list[str]
    session_id: str | None = None


# ── Analysis Schemas ──────────────────────────────────────────────────────────

class RootCauseAnalysisRequest(BaseSchema):
    incident_id: str
    include_rag: bool = True
    max_similar: int = 5


class RootCauseAnalysisResponse(BaseSchema):
    incident_id: str
    root_causes: list[RootCause]
    recommended_fixes: list[str]
    ai_confidence: float
    ai_summary: str
    timeline: list[TimelineEvent]
    similar_incidents: list[dict] | None
    model_used: str
    analysis_time_ms: float
