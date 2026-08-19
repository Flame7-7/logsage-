"""
LogSage AI — Sample Data Generator
Generates realistic log entries for multiple scenarios:
discord_bot, redis, database, gateway, worker, mixed
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from models.models import LogEntry, LogLevel, LogSource


# ── Message templates ─────────────────────────────────────────────────────────

REDIS_LOGS = [
    ("ERROR", "redis", "Redis connection timeout after 5000ms"),
    ("ERROR", "redis", "ECONNREFUSED 127.0.0.1:6379 - Redis unavailable"),
    ("WARNING", "redis", "Redis reconnecting (attempt 3/5)"),
    ("WARNING", "cache", "Cache miss rate exceeded 80% threshold"),
    ("ERROR", "redis", "Redis pool exhausted: all 50 connections in use"),
    ("INFO", "redis", "Redis connection restored after 12s"),
    ("WARNING", "cache", "Cache invalidation storm detected: 2000 keys/sec"),
    ("ERROR", "redis", "Redis CLUSTER SETSLOT failed: node unreachable"),
    ("CRITICAL", "redis", "Redis OOM: used_memory > maxmemory, evicting keys"),
    ("WARNING", "redis", "Slow command detected: SMEMBERS took 890ms"),
]

GATEWAY_LOGS = [
    ("ERROR", "gateway", "Gateway reconnect spike: 47 reconnections in 60s"),
    ("WARNING", "gateway", "Shard [3] heartbeat timeout — reconnecting"),
    ("ERROR", "gateway", "WebSocket connection closed unexpectedly: code 1006"),
    ("WARNING", "shard", "Shard overload: 4200 events/s exceeds capacity"),
    ("ERROR", "gateway", "Discord gateway disconnected: opcode 9 (invalid session)"),
    ("WARNING", "gateway", "Rate limited on IDENTIFY: retry in 5000ms"),
    ("ERROR", "shard", "Shard [1] went offline at 2024-01-15T14:32:01Z"),
    ("INFO", "gateway", "Gateway reconnected after 8.2s downtime"),
    ("WARNING", "gateway", "High latency detected: gateway ping 840ms"),
    ("CRITICAL", "gateway", "All shards disconnected — gateway outage"),
]

DATABASE_LOGS = [
    ("ERROR", "db", "DB connection pool exhausted: 100/100 connections active"),
    ("ERROR", "db", "Query timeout: SELECT on logs table took 32s"),
    ("WARNING", "db", "Slow query detected: full table scan on 50M rows"),
    ("ERROR", "db", "Deadlock detected: transaction rolled back"),
    ("CRITICAL", "db", "Disk usage at 95%: write operations degraded"),
    ("WARNING", "db", "Replication lag: replica 4.2s behind primary"),
    ("ERROR", "db", "PostgreSQL FATAL: too many connections (max 200)"),
    ("WARNING", "db", "Index bloat detected on log_entries: 40% overhead"),
    ("ERROR", "db", "Connection reset by peer during long-running transaction"),
    ("INFO", "db", "Auto-vacuum completed on incidents table"),
]

WORKER_LOGS = [
    ("ERROR", "worker", "Celery worker crashed: OOM at 8.2GB heap"),
    ("WARNING", "worker", "Task queue depth: 1247 pending tasks"),
    ("ERROR", "worker", "Task embedding_batch_abc123 failed after 3 retries"),
    ("CRITICAL", "worker", "All workers unresponsive — triggering restart"),
    ("WARNING", "worker", "Worker heartbeat lost for node worker-3"),
    ("ERROR", "worker", "Memory leak detected: worker RSS growing 50MB/hour"),
    ("WARNING", "worker", "Task processing latency P99: 12.4s (threshold: 5s)"),
    ("INFO", "worker", "Worker pool scaled up: 4 → 8 workers"),
    ("ERROR", "worker", "Broker connection lost: Redis unavailable"),
    ("WARNING", "worker", "Task retry storm: 500 tasks retrying simultaneously"),
]

API_LOGS = [
    ("WARNING", "api", "Rate limit exceeded for IP 192.168.1.100: 429 Too Many Requests"),
    ("ERROR", "api", "Unhandled exception in POST /logs/upload: MemoryError"),
    ("WARNING", "api", "Request timeout: POST /analyze took 30.1s"),
    ("INFO", "api", "New ingestion session started: session_abc123"),
    ("ERROR", "api", "Authentication failed: invalid JWT signature"),
    ("WARNING", "api", "High request volume: 2500 req/s (limit: 2000)"),
    ("ERROR", "api", "Service unavailable: downstream dependency timeout"),
    ("INFO", "api", "Health check passed: all services operational"),
]

MIXED_NORMAL = [
    ("INFO", "api", "Request processed: POST /logs/upload 200 OK in 142ms"),
    ("INFO", "worker", "Embedding batch completed: 64 entries in 1.2s"),
    ("INFO", "db", "Query executed: SELECT incidents in 23ms"),
    ("DEBUG", "cache", "Cache hit: incident_summary_abc123"),
    ("INFO", "gateway", "Heartbeat acknowledged: shard [0] latency 42ms"),
    ("INFO", "redis", "Pipeline executed: 12 commands in 3ms"),
]


def _make_entry(
    level_str: str,
    service: str,
    message: str,
    session_id: str,
    timestamp: datetime,
) -> LogEntry:
    level_map = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
        "CRITICAL": LogLevel.CRITICAL,
    }
    return LogEntry(
        id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=timestamp,
        level=level_map.get(level_str, LogLevel.INFO),
        source=LogSource.SIMULATED,
        service=service,
        message=message,
        raw_line=f"[{timestamp.strftime('%Y-%m-%dT%H:%M:%S')}] [{level_str}] [{service}] {message}",
        extra_fields={"simulated": True, "scenario": "auto"},
    )


SCENARIO_POOLS: dict[str, list[tuple[str, str, str]]] = {
    "redis": REDIS_LOGS,
    "gateway": GATEWAY_LOGS,
    "database": DATABASE_LOGS,
    "worker": WORKER_LOGS,
    "api": API_LOGS,
    "mixed": REDIS_LOGS + GATEWAY_LOGS + DATABASE_LOGS + WORKER_LOGS + API_LOGS + MIXED_NORMAL * 3,
    "incident": (
        REDIS_LOGS[:5] + GATEWAY_LOGS[:5] + DATABASE_LOGS[:3] + WORKER_LOGS[:3]
    ),
}


def generate_sample_logs(
    count: int = 200,
    scenario: str = "mixed",
    session_id: str | None = None,
    start_time: datetime | None = None,
) -> list[LogEntry]:
    """
    Generate realistic sample log entries.

    Args:
        count: Number of entries to generate
        scenario: One of redis|gateway|database|worker|api|mixed|incident
        session_id: Override session ID
        start_time: Start timestamp (defaults to now - count seconds)
    """
    pool = SCENARIO_POOLS.get(scenario, SCENARIO_POOLS["mixed"])
    session_id = session_id or str(uuid.uuid4())
    start_time = start_time or (datetime.utcnow() - timedelta(seconds=count))

    entries: list[LogEntry] = []
    for i in range(count):
        # Weighted random selection — more errors during "incident" scenarios
        if scenario == "incident" and random.random() < 0.7:
            template = random.choice([t for t in pool if t[0] in ("ERROR", "CRITICAL", "WARNING")])
        else:
            template = random.choice(pool)

        level_str, service, base_message = template

        # Add slight variation to messages
        jitter = random.choice(["", " (attempt 2)", " after 3s", " [retry]", ""])
        message = base_message + jitter

        # Realistic timestamp with minor jitter
        ts = start_time + timedelta(seconds=i + random.uniform(0, 0.9))

        entries.append(_make_entry(level_str, service, message, session_id, ts))

    return entries


def get_discord_incident_scenario(session_id: str | None = None) -> list[LogEntry]:
    """
    Pre-built Discord bot incident scenario:
    Redis timeout → Gateway reconnect spike → Shard overload → Worker crash
    """
    session_id = session_id or str(uuid.uuid4())
    base = datetime.utcnow() - timedelta(minutes=10)

    events: list[tuple[int, str, str, str]] = [
        # (offset_seconds, level, service, message)
        (0, "INFO", "api", "System startup: all services healthy"),
        (60, "WARNING", "redis", "Redis latency spike: 450ms average"),
        (62, "WARNING", "redis", "Redis reconnecting (attempt 1/5)"),
        (63, "ERROR", "redis", "Redis connection timeout after 5000ms"),
        (65, "ERROR", "redis", "Redis pool exhausted: all 50 connections in use"),
        (67, "WARNING", "cache", "Cache miss rate exceeded 80% threshold"),
        (70, "ERROR", "gateway", "WebSocket connection closed unexpectedly: code 1006"),
        (71, "WARNING", "gateway", "Shard [3] heartbeat timeout — reconnecting"),
        (72, "WARNING", "shard", "Shard overload: 4200 events/s exceeds capacity"),
        (73, "ERROR", "gateway", "Gateway reconnect spike: 12 reconnections in 30s"),
        (75, "ERROR", "db", "DB connection pool exhausted: 100/100 connections active"),
        (76, "ERROR", "db", "Query timeout: SELECT on logs table took 32s"),
        (78, "WARNING", "worker", "Task queue depth: 1247 pending tasks"),
        (80, "ERROR", "worker", "Task embedding_batch_abc123 failed after 3 retries"),
        (82, "CRITICAL", "worker", "All workers unresponsive — triggering restart"),
        (83, "CRITICAL", "gateway", "All shards disconnected — gateway outage"),
        (84, "CRITICAL", "db", "Disk usage at 95%: write operations degraded"),
        (120, "INFO", "redis", "Redis connection restored after 12s"),
        (122, "INFO", "gateway", "Gateway reconnected after 8.2s downtime"),
        (125, "INFO", "worker", "Worker pool scaled up: 4 → 8 workers"),
        (130, "INFO", "api", "System recovery: services coming back online"),
    ]

    entries = []
    for offset, level, service, message in events:
        ts = base + timedelta(seconds=offset)
        entries.append(_make_entry(level, service, message, session_id, ts))

    return entries
