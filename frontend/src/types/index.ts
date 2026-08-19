// LogSage AI — TypeScript Types

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type LogSource = "file_upload" | "websocket" | "api" | "simulated";
export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "investigating" | "resolved" | "false_positive";
export type AlertStatus = "firing" | "resolved" | "suppressed";

// ── Log Entry ─────────────────────────────────────────────────────────────────

export interface LogEntry {
  id: string;
  session_id: string;
  timestamp: string;
  level: LogLevel;
  source: LogSource;
  service: string | null;
  message: string;
  is_anomaly: boolean;
  anomaly_score: number | null;
  cluster_id: string | null;
  incident_id: string | null;
  created_at: string;
}

// ── Cluster ───────────────────────────────────────────────────────────────────

export interface Cluster {
  id: string;
  name: string;
  description: string | null;
  log_count: number;
  severity: IncidentSeverity;
  representative_messages: string[] | null;
  tags: string[] | null;
  first_seen: string;
  last_seen: string;
  created_at: string;
}

export interface ClusterListResponse {
  clusters: Cluster[];
  total: number;
}

// ── Incident ──────────────────────────────────────────────────────────────────

export interface RootCause {
  cause: string;
  confidence: number;
  category: string | null;
}

export interface TimelineEvent {
  timestamp: string;
  event: string;
  level: string | null;
  service: string | null;
}

export interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: IncidentSeverity;
  status: IncidentStatus;
  cluster_id: string | null;
  root_causes: RootCause[] | null;
  recommended_fixes: string[] | null;
  timeline: TimelineEvent[] | null;
  ai_confidence: number | null;
  ai_summary: string | null;
  affected_services: string[] | null;
  log_count: number;
  detected_at: string;
  resolved_at: string | null;
  created_at: string;
}

export interface IncidentListResponse {
  incidents: Incident[];
  total: number;
  open_count: number;
  critical_count: number;
}

// ── Alert ─────────────────────────────────────────────────────────────────────

export interface Alert {
  id: string;
  incident_id: string | null;
  alert_type: string;
  title: string;
  message: string;
  severity: IncidentSeverity;
  status: AlertStatus;
  threshold_value: number | null;
  actual_value: number | null;
  fired_at: string;
  resolved_at: string | null;
}

export interface AlertListResponse {
  alerts: Alert[];
  total: number;
  firing_count: number;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface MetricsSnapshot {
  timestamp: string;
  events_per_second: number;
  incident_count: number;
  open_incident_count: number;
  critical_incident_count: number;
  cluster_count: number;
  total_log_count: number;
  error_rate: number;
  queue_size: number;
  processing_latency_ms: number;
  anomaly_count: number;
}

export interface ErrorHeatmapPoint {
  hour: number;
  day: number;
  count: number;
  severity?: string;
}

export interface DashboardData {
  metrics: MetricsSnapshot;
  recent_incidents: Incident[];
  top_clusters: Cluster[];
  error_heatmap: ErrorHeatmapPoint[];
  events_timeline: Record<string, unknown>[];
}

// ── Root Cause Analysis ───────────────────────────────────────────────────────

export interface RCAResponse {
  incident_id: string;
  root_causes: RootCause[];
  recommended_fixes: string[];
  ai_confidence: number;
  ai_summary: string;
  timeline: TimelineEvent[];
  similar_incidents: Record<string, unknown>[] | null;
  model_used: string;
  analysis_time_ms: number;
}

export interface IngestionResult {
  session_id: string;
  total_lines: number;
  processed_lines: number;
  error_lines: number;
  incidents_detected: number;
  clusters_updated: number;
  processing_time_ms: number;
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

export interface WSMessage {
  type: "log_entry" | "incident" | "alert" | "metrics" | "heartbeat" | "ack";
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface LiveLogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  service: string | null;
  message: string;
  is_anomaly: boolean;
}
