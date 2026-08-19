"""
LogSage AI — Celery Workers
Background tasks: embedding generation, clustering, RCA, scheduled cleanup.
"""

from __future__ import annotations

import asyncio

import structlog
from celery import Celery
from celery.schedules import crontab

from core.config import settings

logger = structlog.get_logger(__name__)

# ── Celery App ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "logsage",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.tasks.process_embedding_batch": {"queue": "embeddings"},
        "workers.tasks.run_clustering": {"queue": "clustering"},
        "workers.tasks.run_root_cause_analysis": {"queue": "ai"},
        "workers.tasks.cleanup_old_embeddings": {"queue": "maintenance"},
    },
    beat_schedule={
        "cleanup-old-embeddings": {
            "task": "workers.tasks.cleanup_old_embeddings",
            "schedule": crontab(hour=3, minute=0),
        },
        "process-pending-embeddings": {
            "task": "workers.tasks.process_pending_embeddings",
            "schedule": 30.0,  # every 30 seconds
        },
    },
)


def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
