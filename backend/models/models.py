"""
LogSage AI — ORM Models
Full database schema: logs, incidents, clusters, embeddings, alerts, summaries.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(str, enum.Enum):
    FILE_UPLOAD = "file_upload"
    WEBSOCKET = "websocket"
    API = "api"
    SIMULATED = "simulated"


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class AlertStatus(str, enum.Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# ── Log Entry ─────────────────────────────────────────────────────────────────

class LogEntry(Base):
    __tablename__ = "log_entries"
    __table_args__ = (
        Index("ix_log_entries_timestamp", "timestamp"),
        Index("ix_log_entries_level", "level"),
        Index("ix_log_entries_source", "source"),
        Index("ix_log_entries_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel), nullable=False)
    source: Mapped[LogSource] = mapped_column(Enum(LogSource), nullable=False)
    service: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_line: Mapped[str | None] = mapped_column(Text)
    extra_fields: Mapped[dict | None] = mapped_column(JSON)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    cluster_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True
    )
    incident_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    cluster: Mapped["Cluster | None"] = relationship(back_populates="log_entries")
    incident: Mapped["Incident | None"] = relationship(back_populates="log_entries")
    embedding: Mapped["LogEmbedding | None"] = relationship(
        back_populates="log_entry", cascade="all, delete-orphan"
    )


# ── Cluster ───────────────────────────────────────────────────────────────────

class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    centroid_vector_id: Mapped[str | None] = mapped_column(String(256))
    log_count: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity), default=IncidentSeverity.LOW
    )
    representative_messages: Mapped[list | None] = mapped_column(JSON)
    tags: Mapped[list | None] = mapped_column(JSON)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    log_entries: Mapped[list["LogEntry"]] = relationship(back_populates="cluster")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="cluster")


# ── Incident ──────────────────────────────────────────────────────────────────

class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_severity", "severity"),
        Index("ix_incidents_detected_at", "detected_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity), nullable=False, default=IncidentSeverity.MEDIUM
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN
    )
    cluster_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True
    )

    # AI-generated fields
    root_causes: Mapped[list | None] = mapped_column(JSON)  # [{cause, confidence}]
    recommended_fixes: Mapped[list | None] = mapped_column(JSON)  # [str]
    timeline: Mapped[list | None] = mapped_column(JSON)  # [{timestamp, event}]
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_summary: Mapped[str | None] = mapped_column(Text)

    # Metrics
    affected_services: Mapped[list | None] = mapped_column(JSON)
    log_count: Mapped[int] = mapped_column(Integer, default=0)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cluster: Mapped["Cluster | None"] = relationship(back_populates="incidents")
    log_entries: Mapped[list["LogEntry"]] = relationship(back_populates="incident")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="incident")
    summary: Mapped["IncidentSummary | None"] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


# ── Log Embedding ─────────────────────────────────────────────────────────────

class LogEmbedding(Base):
    __tablename__ = "log_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    log_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("log_entries.id", ondelete="CASCADE"), unique=True
    )
    chroma_id: Mapped[str | None] = mapped_column(String(256))
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    log_entry: Mapped["LogEntry"] = relationship(back_populates="embedding")


# ── Alert ─────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_fired_at", "fired_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    incident_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.FIRING
    )
    threshold_value: Mapped[float | None] = mapped_column(Float)
    actual_value: Mapped[float | None] = mapped_column(Float)
    alert_metadata: Mapped[dict | None] = mapped_column(JSON)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    incident: Mapped["Incident | None"] = relationship(back_populates="alerts")


# ── Incident Summary ──────────────────────────────────────────────────────────

class IncidentSummary(Base):
    __tablename__ = "incident_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="CASCADE"), unique=True
    )
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    technical_details: Mapped[str | None] = mapped_column(Text)
    impact_assessment: Mapped[str | None] = mapped_column(Text)
    prevention_steps: Mapped[list | None] = mapped_column(JSON)
    similar_past_incidents: Mapped[list | None] = mapped_column(JSON)
    model_used: Mapped[str] = mapped_column(String(128), nullable=False)
    token_usage: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    incident: Mapped["Incident"] = relationship(back_populates="summary")


# ── Ingestion Session ─────────────────────────────────────────────────────────

class IngestionSession(Base):
    __tablename__ = "ingestion_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source: Mapped[LogSource] = mapped_column(Enum(LogSource), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(512))
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    processed_lines: Mapped[int] = mapped_column(Integer, default=0)
    error_lines: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="processing")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )