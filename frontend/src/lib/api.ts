// LogSage AI — API Client

import axios from "axios";
import useSWR from "swr";
import type {
  AlertListResponse,
  ClusterListResponse,
  DashboardData,
  IncidentListResponse,
  IngestionResult,
  MetricsSnapshot,
  RCAResponse,
  Incident,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// ── Fetcher for SWR ───────────────────────────────────────────────────────────

const fetcher = (url: string) =>
  api.get(url).then((r) => r.data);

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useDashboard(refreshInterval = 5000) {
  return useSWR<DashboardData>("/metrics/dashboard", fetcher, { refreshInterval });
}

export function useMetrics(refreshInterval = 3000) {
  return useSWR<MetricsSnapshot>("/metrics", fetcher, { refreshInterval });
}

export function useIncidents(params?: {
  status?: string;
  severity?: string;
  offset?: number;
  limit?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  const key = `/incidents?${qs.toString()}`;
  return useSWR<IncidentListResponse>(key, fetcher, { refreshInterval: 10_000 });
}

export function useIncident(id: string | null) {
  return useSWR<Incident>(id ? `/incidents/${id}` : null, fetcher);
}

export function useClusters(limit = 20) {
  return useSWR<ClusterListResponse>(`/clusters?limit=${limit}`, fetcher, {
    refreshInterval: 15_000,
  });
}

export function useAlerts() {
  return useSWR<AlertListResponse>("/alerts", fetcher, { refreshInterval: 5_000 });
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export async function uploadLogFile(file: File): Promise<IngestionResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post("/logs/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function simulateLogs(
  count: number,
  scenario: string
): Promise<IngestionResult> {
  const res = await api.post(
    `/logs/simulate?count=${count}&scenario=${scenario}`
  );
  return res.data;
}

export async function triggerAnalysis(
  incidentId: string,
  useRag = true
): Promise<RCAResponse> {
  const res = await api.post(
    `/incidents/${incidentId}/analyze?use_rag=${useRag}`
  );
  return res.data;
}

export async function updateIncidentStatus(
  incidentId: string,
  status: string
): Promise<Incident> {
  const res = await api.patch(`/incidents/${incidentId}`, { status });
  return res.data;
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

export function createLiveSocket(): WebSocket {
  return new WebSocket(`${WS_BASE}/api/v1/live`);
}

// ── Utilities ─────────────────────────────────────────────────────────────────

export const SEVERITY_COLORS: Record<string, string> = {
  low: "text-blue-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

export const SEVERITY_BG: Record<string, string> = {
  low: "bg-blue-400/10 border-blue-400/30",
  medium: "bg-yellow-400/10 border-yellow-400/30",
  high: "bg-orange-400/10 border-orange-400/30",
  critical: "bg-red-400/10 border-red-400/30",
};

export const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "text-slate-400",
  INFO: "text-sage-400",
  WARNING: "text-yellow-400",
  ERROR: "text-red-400",
  CRITICAL: "text-red-300 font-bold",
};

export const STATUS_COLORS: Record<string, string> = {
  open: "text-red-400",
  investigating: "text-yellow-400",
  resolved: "text-sage-400",
  false_positive: "text-slate-400",
};
