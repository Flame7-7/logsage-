"use client";

import { Activity, AlertTriangle, Layers, TrendingUp, Zap } from "lucide-react";
import { useMetrics } from "@/lib/api";
import { clsx } from "clsx";

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "sage",
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color?: "sage" | "red" | "yellow" | "blue";
}) {
  const colors = {
    sage: "text-sage-400 bg-sage-500/10",
    red: "text-red-400 bg-red-500/10",
    yellow: "text-yellow-400 bg-yellow-500/10",
    blue: "text-blue-400 bg-blue-500/10",
  };

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-r border-slate-800/60 last:border-r-0">
      <div className={clsx("p-1.5 rounded-md", colors[color])}>
        <Icon className={clsx("w-3.5 h-3.5", colors[color].split(" ")[0])} />
      </div>
      <div>
        <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
        <div className="text-sm font-semibold text-slate-100 font-mono">{value}</div>
        {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
      </div>
    </div>
  );
}

export default function MetricsBar() {
  const { data } = useMetrics();

  return (
    <div className="h-14 flex items-center bg-slate-900/60 border-b border-slate-800/60 backdrop-blur-sm overflow-x-auto">
      <StatCard
        icon={Activity}
        label="Events/sec"
        value={data?.events_per_second?.toFixed(1) ?? "—"}
        color="sage"
      />
      <StatCard
        icon={AlertTriangle}
        label="Open Incidents"
        value={data?.open_incident_count ?? "—"}
        sub={`${data?.critical_incident_count ?? 0} critical`}
        color={data?.critical_incident_count ? "red" : "yellow"}
      />
      <StatCard
        icon={Layers}
        label="Clusters"
        value={data?.cluster_count ?? "—"}
        color="blue"
      />
      <StatCard
        icon={TrendingUp}
        label="Error Rate"
        value={data ? `${(data.error_rate * 100).toFixed(1)}%` : "—"}
        color={(data?.error_rate ?? 0) > 0.1 ? "red" : "sage"}
      />
      <StatCard
        icon={Zap}
        label="Total Logs"
        value={data?.total_log_count?.toLocaleString() ?? "—"}
        color="sage"
      />

      {/* Queue indicator */}
      <div className="ml-auto flex items-center gap-2 px-4">
        {data?.queue_size !== undefined && data.queue_size > 0 && (
          <span className="text-[10px] font-mono text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded-full border border-yellow-400/20">
            Queue: {data.queue_size}
          </span>
        )}
        <span className="flex items-center gap-1.5 text-[10px] text-sage-400 font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-sage-400 animate-pulse" />
          LIVE
        </span>
      </div>
    </div>
  );
}