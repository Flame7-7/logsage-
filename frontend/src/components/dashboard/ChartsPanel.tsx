"use client";

import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useDashboard } from "@/lib/api";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card-glass rounded-xl p-5">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
        {title}
      </h3>
      {children}
    </div>
  );
}

const SEVERITY_FILL: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
};

export default function ChartsPanel() {
  const { data, isLoading } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-sage-400 animate-spin" />
      </div>
    );
  }

  // Build mock time series from metrics (real app would store this in DB)
  const now = Date.now();
  const timeSeriesData = Array.from({ length: 20 }, (_, i) => ({
    time: format(new Date(now - (19 - i) * 30_000), "HH:mm:ss"),
    events: Math.round(
      (data?.metrics.events_per_second ?? 2) * 60 + Math.random() * 50 - 25
    ),
    errors: Math.round(
      (data?.metrics.error_rate ?? 0.05) *
        ((data?.metrics.events_per_second ?? 2) * 60) +
        Math.random() * 5
    ),
  }));

  // Cluster bar chart data
  const clusterData = (data?.top_clusters ?? []).map((c) => ({
    name: c.name.length > 18 ? c.name.slice(0, 18) + "…" : c.name,
    count: c.log_count,
    severity: c.severity,
  }));

  // Incident by severity
  const incidentData = [
    { label: "Critical", count: data?.metrics.critical_incident_count ?? 0, color: "#ef4444" },
    {
      label: "Open",
      count: (data?.metrics.open_incident_count ?? 0) - (data?.metrics.critical_incident_count ?? 0),
      color: "#f97316",
    },
    {
      label: "Total",
      count: data?.metrics.incident_count ?? 0,
      color: "#22c55e",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Recent incidents summary */}
      <div className="grid grid-cols-3 gap-4">
        {incidentData.map((item) => (
          <div key={item.label} className="card-glass rounded-xl p-4 text-center">
            <div className="text-3xl font-bold font-mono" style={{ color: item.color }}>
              {item.count}
            </div>
            <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">
              {item.label} Incidents
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Events timeline */}
        <SectionCard title="Events / Errors Timeline (last 10 min)">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={timeSeriesData}>
              <defs>
                <linearGradient id="eventsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="errorsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: "#64748b" }}
                interval={4}
              />
              <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
              <Tooltip
                contentStyle={{
                  background: "#0f1629",
                  border: "1px solid rgba(148,163,184,0.15)",
                  borderRadius: 8,
                  fontSize: 11,
                }}
              />
              <Area
                type="monotone"
                dataKey="events"
                stroke="#22c55e"
                strokeWidth={1.5}
                fill="url(#eventsGrad)"
                name="Events"
              />
              <Area
                type="monotone"
                dataKey="errors"
                stroke="#ef4444"
                strokeWidth={1.5}
                fill="url(#errorsGrad)"
                name="Errors"
              />
            </AreaChart>
          </ResponsiveContainer>
        </SectionCard>

        {/* Top clusters */}
        <SectionCard title="Top Clusters by Volume">
          {clusterData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={clusterData} layout="vertical">
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(148,163,184,0.06)"
                  horizontal={false}
                />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis
                  dataKey="name"
                  type="category"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  width={120}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0f1629",
                    border: "1px solid rgba(148,163,184,0.15)",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="count" name="Events" radius={[0, 4, 4, 0]}>
                  {clusterData.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={SEVERITY_FILL[entry.severity] ?? "#22c55e"}
                      fillOpacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-sm text-slate-500">
              No clusters yet — ingest some logs to get started
            </div>
          )}
        </SectionCard>
      </div>

      {/* Recent incidents table */}
      <SectionCard title="Recent Incidents">
        {data?.recent_incidents.length ? (
          <div className="space-y-2">
            {data.recent_incidents.map((inc) => (
              <div
                key={inc.id}
                className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/40 hover:bg-slate-800/70 transition-colors"
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: SEVERITY_FILL[inc.severity] }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-slate-200 truncate">{inc.title}</div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    {format(new Date(inc.detected_at), "MMM d, HH:mm:ss")} ·{" "}
                    {inc.log_count} logs
                  </div>
                </div>
                <span
                  className="text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full border"
                  style={{
                    color: SEVERITY_FILL[inc.severity],
                    borderColor: `${SEVERITY_FILL[inc.severity]}40`,
                    background: `${SEVERITY_FILL[inc.severity]}10`,
                  }}
                >
                  {inc.severity}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-slate-500 text-center py-8">
            No incidents detected yet
          </div>
        )}
      </SectionCard>
    </div>
  );
}
