"""
LogSage AI — FastAPI Application
Production-grade entrypoint with lifespan, middleware, and observability.
"""

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST

from api.routes.routes import router
from core.config import settings
from core.database import close_db, init_db
from core.logging import setup_logging
from core.metrics import (
    get_metrics_output,
    http_request_duration,
    request_count,
    websocket_connections,
)
from core.redis_client import close_redis, get_redis

setup_logging()
logger = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LogSage AI starting up", version=settings.APP_VERSION, env=settings.ENVIRONMENT)

    # Initialize connections
    await get_redis()
    logger.info("Redis connected")

    # Auto-create all tables
    await init_db()
    logger.info("Database tables ready")

    # Pre-warm embedding model in background
    try:
        from ai.embeddings.embedding_service import get_embedding_model
        import asyncio
        asyncio.create_task(get_embedding_model())
        logger.info("Embedding model pre-warm scheduled")
    except Exception as e:
        logger.warning("Could not pre-warm model", error=str(e))

    yield

    logger.info("LogSage AI shutting down")
    await close_redis()
    await close_db()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered log analysis and incident detection platform",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed = time.monotonic() - start

    endpoint = request.url.path
    method = request.method
    status = str(response.status_code)

    request_count.labels(method=method, endpoint=endpoint, status_code=status).inc()
    http_request_duration.labels(method=method, endpoint=endpoint).observe(elapsed)

    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    import uuid
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready")
async def ready() -> dict:
    """Readiness probe — checks DB + Redis."""
    try:
        r = await get_redis()
        await r.ping()
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Not ready: {e}")


@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """Expose Prometheus metrics."""
    data = get_metrics_output()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)