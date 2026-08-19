"""
LogSage AI — Repositories
Generic + specialized async repositories using the repository pattern.
"""

from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import Base
from models.models import (
    Alert,
    AlertStatus,
    Cluster,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IngestionSession,
    LogEmbedding,
    LogEntry,
    LogSource,
    IncidentSummary,
)

T = TypeVar("T", bound=Base)


# ── Generic Repository ────────────────────────────────────────────────────────

class BaseRepository(Generic[T]):
    def __init__(self, model: type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: str) -> T | None:
        return await self.session.get(self.model, id)

    async def list(self, offset: int = 0, limit: int = 50) -> list[T]:
        result = await self.session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: T) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()


# ── Log Repository ────────────────────────────────────────────────────────────

class LogRepository(BaseRepository[LogEntry]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LogEntry, session)

    async def bulk_create(self, entries: list[LogEntry]) -> list[LogEntry]:
        self.session.add_all(entries)
        await self.session.flush()
        return entries

    async def get_by_session(
        self,
        session_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> list[LogEntry]:
        result = await self.session.execute(
            select(LogEntry)
            .where(LogEntry.session_id == session_id)
            .order_by(LogEntry.timestamp)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_anomalies(
        self,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[LogEntry]:
        q = select(LogEntry).where(LogEntry.is_anomaly.is_(True))
        if since:
            q = q.where(LogEntry.timestamp >= since)
        q = q.order_by(LogEntry.timestamp.desc()).limit(limit)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count_by_level_in_window(
        self, window_seconds: int = 300
    ) -> dict[str, int]:
        since = datetime.utcnow() - timedelta(seconds=window_seconds)
        result = await self.session.execute(
            select(LogEntry.level, func.count(LogEntry.id))
            .where(LogEntry.timestamp >= since)
            .group_by(LogEntry.level)
        )
        return {str(row[0]): row[1] for row in result.all()}

    async def get_events_per_second(self) -> float:
        since = datetime.utcnow() - timedelta(seconds=60)
        result = await self.session.execute(
            select(func.count(LogEntry.id)).where(LogEntry.timestamp >= since)
        )
        count = result.scalar_one()
        return count / 60.0

    async def get_unclustered(self, limit: int = 200) -> list[LogEntry]:
        result = await self.session.execute(
            select(LogEntry)
            .where(LogEntry.cluster_id.is_(None))
            .order_by(LogEntry.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_without_embedding(self, limit: int = 64) -> list[LogEntry]:
        subq = select(LogEmbedding.log_entry_id)
        result = await self.session.execute(
            select(LogEntry)
            .where(LogEntry.id.not_in(subq))
            .order_by(LogEntry.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_error_heatmap(self) -> list[dict]:
        since = datetime.utcnow() - timedelta(days=7)
        result = await self.session.execute(
            select(
                func.extract("hour", LogEntry.timestamp).label("hour"),
                func.extract("dow", LogEntry.timestamp).label("day"),
                func.count(LogEntry.id).label("count"),
            )
            .where(
                LogEntry.timestamp >= since,
                LogEntry.level.in_(["ERROR", "CRITICAL"]),
            )
            .group_by("hour", "day")
        )
        return [{"hour": int(r[0]), "day": int(r[1]), "count": r[2]} for r in result.all()]


# ── Cluster Repository ────────────────────────────────────────────────────────

class ClusterRepository(BaseRepository[Cluster]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Cluster, session)

    async def get_top_by_count(self, limit: int = 10) -> list[Cluster]:
        result = await self.session.execute(
            select(Cluster).order_by(Cluster.log_count.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def increment_count(self, cluster_id: str) -> None:
        await self.session.execute(
            update(Cluster)
            .where(Cluster.id == cluster_id)
            .values(log_count=Cluster.log_count + 1, last_seen=datetime.utcnow())
        )


# ── Incident Repository ───────────────────────────────────────────────────────

class IncidentRepository(BaseRepository[Incident]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Incident, session)

    async def get_with_relations(self, incident_id: str) -> Incident | None:
        result = await self.session.execute(
            select(Incident)
            .options(
                selectinload(Incident.alerts),
                selectinload(Incident.summary),
            )
            .where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list_open(self, limit: int = 50) -> list[Incident]:
        result = await self.session.execute(
            select(Incident)
            .where(Incident.status == IncidentStatus.OPEN)
            .order_by(Incident.detected_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_with_filters(
        self,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Incident], int]:
        q = select(Incident)
        count_q = select(func.count()).select_from(Incident)

        if status:
            q = q.where(Incident.status == status)
            count_q = count_q.where(Incident.status == status)
        if severity:
            q = q.where(Incident.severity == severity)
            count_q = count_q.where(Incident.severity == severity)

        q = q.order_by(Incident.detected_at.desc()).offset(offset).limit(limit)

        items = list((await self.session.execute(q)).scalars().all())
        total = (await self.session.execute(count_q)).scalar_one()
        return items, total

    async def count_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(Incident.status, func.count(Incident.id)).group_by(Incident.status)
        )
        return {str(row[0]): row[1] for row in result.all()}


# ── Alert Repository ──────────────────────────────────────────────────────────

class AlertRepository(BaseRepository[Alert]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Alert, session)

    async def get_firing(self, limit: int = 50) -> list[Alert]:
        result = await self.session.execute(
            select(Alert)
            .where(Alert.status == AlertStatus.FIRING)
            .order_by(Alert.fired_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_firing(self) -> int:
        result = await self.session.execute(
            select(func.count(Alert.id)).where(Alert.status == AlertStatus.FIRING)
        )
        return result.scalar_one()


# ── Embedding Repository ──────────────────────────────────────────────────────

class EmbeddingRepository(BaseRepository[LogEmbedding]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LogEmbedding, session)

    async def get_by_log_id(self, log_entry_id: str) -> LogEmbedding | None:
        result = await self.session.execute(
            select(LogEmbedding).where(LogEmbedding.log_entry_id == log_entry_id)
        )
        return result.scalar_one_or_none()


# ── Session Repository ────────────────────────────────────────────────────────

class IngestionSessionRepository(BaseRepository[IngestionSession]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(IngestionSession, session)
