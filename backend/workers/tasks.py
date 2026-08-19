"""
LogSage AI — Celery Tasks
"""

from __future__ import annotations

import structlog

from workers.celery_app import celery_app, run_async

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_embedding_batch(self, log_ids: list[str]) -> dict:
    """Embed a batch of log entry IDs stored in DB."""
    async def _run():
        from ai.embeddings.embedding_service import embed_log_entries
        from core.database import get_session_ctx
        from repositories.repositories import LogRepository

        async with get_session_ctx() as session:
            repo = LogRepository(session)
            entries = []
            for log_id in log_ids:
                entry = await repo.get(log_id)
                if entry:
                    entries.append(entry)

            if not entries:
                return {"embedded": 0}

            embedding_map = await embed_log_entries(entries)

            # Persist embedding records
            from datetime import datetime
            from models.models import LogEmbedding
            from core.config import settings
            import uuid
            for log_id, vector in embedding_map.items():
                emb = LogEmbedding(
                    id=str(uuid.uuid4()),
                    log_entry_id=log_id,
                    model_name=settings.EMBEDDING_MODEL,
                    embedding_dimension=len(vector),
                )
                session.add(emb)

            return {"embedded": len(embedding_map)}

    try:
        return run_async(_run())
    except Exception as exc:
        logger.error("Embedding task failed", error=str(exc), log_ids=log_ids[:5])
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def run_clustering(self, session_id: str) -> dict:
    """Re-run clustering for all unclustered entries in a session."""
    async def _run():
        from ai.clustering import cluster_log_entries
        from core.database import get_session_ctx
        from repositories.repositories import LogRepository

        async with get_session_ctx() as session:
            repo = LogRepository(session)
            entries = await repo.get_unclustered(limit=500)
            if not entries:
                return {"clusters": 0}
            clusters = await cluster_log_entries(entries, session)
            return {"clusters": len(clusters), "entries_clustered": len(entries)}

    try:
        return run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def run_root_cause_analysis(self, incident_id: str) -> dict:
    """Run AI root cause analysis for an incident."""
    async def _run():
        from ai.analysis.analyzer import analyze_root_cause
        from core.database import get_session_ctx
        from repositories.repositories import IncidentRepository, LogRepository

        async with get_session_ctx() as session:
            incident_repo = IncidentRepository(session)
            log_repo = LogRepository(session)

            incident = await incident_repo.get(incident_id)
            if not incident:
                return {"error": "Incident not found"}

            log_entries = await log_repo.get_by_session(
                incident.cluster_id or incident_id, limit=50
            )
            analysis = await analyze_root_cause(incident, log_entries)

            incident.root_causes = [rc.model_dump() for rc in analysis["root_causes"]]
            incident.recommended_fixes = analysis["recommended_fixes"]
            incident.ai_confidence = analysis["ai_confidence"]
            incident.ai_summary = analysis["ai_summary"]
            await incident_repo.update(incident)

            return {
                "incident_id": incident_id,
                "confidence": analysis["ai_confidence"],
                "root_causes": len(analysis["root_causes"]),
            }

    try:
        return run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task
def process_pending_embeddings() -> dict:
    """Scheduled: process any log entries missing embeddings."""
    async def _run():
        from core.database import get_session_ctx
        from repositories.repositories import LogRepository
        from ai.embeddings.embedding_service import embed_log_entries
        from models.models import LogEmbedding
        from core.config import settings
        import uuid

        async with get_session_ctx() as session:
            repo = LogRepository(session)
            entries = await repo.get_without_embedding(limit=64)
            if not entries:
                return {"processed": 0}

            embedding_map = await embed_log_entries(entries)
            for log_id in embedding_map:
                emb = LogEmbedding(
                    id=str(uuid.uuid4()),
                    log_entry_id=log_id,
                    model_name=settings.EMBEDDING_MODEL,
                    embedding_dimension=settings.EMBEDDING_DIMENSION,
                )
                session.add(emb)

            return {"processed": len(embedding_map)}

    return run_async(_run())


@celery_app.task
def cleanup_old_embeddings() -> dict:
    """Scheduled: remove embeddings for log entries older than 90 days."""
    async def _run():
        from datetime import timedelta, datetime
        from sqlalchemy import delete
        from core.database import get_session_ctx
        from models.models import LogEmbedding, LogEntry

        cutoff = datetime.utcnow() - timedelta(days=90)
        async with get_session_ctx() as session:
            # Subquery: log IDs older than cutoff
            from sqlalchemy import select
            old_ids_q = select(LogEntry.id).where(LogEntry.created_at < cutoff)
            result = await session.execute(old_ids_q)
            old_ids = [r[0] for r in result.all()]

            if not old_ids:
                return {"deleted": 0}

            # Delete embeddings in batches
            deleted = 0
            for i in range(0, len(old_ids), 1000):
                batch = old_ids[i:i+1000]
                await session.execute(
                    delete(LogEmbedding).where(LogEmbedding.log_entry_id.in_(batch))
                )
                deleted += len(batch)

            logger.info("Cleaned up old embeddings", deleted=deleted)
            return {"deleted": deleted}

    return run_async(_run())
