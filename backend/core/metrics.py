"""
LogSage AI — Prometheus Metrics
Counters, histograms, and gauges exposed at /metrics/prometheus.
"""

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── Counters ──────────────────────────────────────────────────────────────────

request_count = Counter(
    "logsage_request_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

log_ingestion_total = Counter(
    "logsage_log_ingestion_total",
    "Total log entries ingested",
    ["source", "level"],
)

incident_count = Counter(
    "logsage_incident_total",
    "Total incidents detected",
    ["severity"],
)

alert_fired_total = Counter(
    "logsage_alert_fired_total",
    "Total alerts fired",
    ["alert_type", "severity"],
)

embedding_processed_total = Counter(
    "logsage_embedding_processed_total",
    "Total log embeddings generated",
)

clustering_runs_total = Counter(
    "logsage_clustering_runs_total",
    "Total clustering runs executed",
)

# ── Gauges ────────────────────────────────────────────────────────────────────

active_incidents = Gauge(
    "logsage_active_incidents",
    "Currently open incidents",
    ["severity"],
)

queue_size = Gauge(
    "logsage_queue_size",
    "Current queue depth",
    ["queue_name"],
)

websocket_connections = Gauge(
    "logsage_websocket_connections",
    "Active WebSocket connections",
)

events_per_second = Gauge(
    "logsage_events_per_second",
    "Current log events per second",
)

error_rate = Gauge(
    "logsage_error_rate",
    "Error rate in 5-minute window (0-1)",
)

# ── Histograms ────────────────────────────────────────────────────────────────

processing_latency = Histogram(
    "logsage_processing_latency_seconds",
    "Log processing pipeline latency",
    ["stage"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

ai_analysis_duration = Histogram(
    "logsage_ai_analysis_duration_seconds",
    "AI root cause analysis duration",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

embedding_batch_duration = Histogram(
    "logsage_embedding_batch_duration_seconds",
    "Embedding batch generation duration",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

http_request_duration = Histogram(
    "logsage_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)


def get_metrics_output() -> bytes:
    """Generate Prometheus text format metrics."""
    return generate_latest(REGISTRY)
