"use client";

import { format } from "date-fns";
import { Layers, Loader2, RefreshCw } from "lucide-react";
import { clsx } from "clsx";
import { useClusters, SEVERITY_BG, SEVERITY_COLORS } from "@/lib/api";
import type { Cluster } from "@/types";
import { useState } from "react";

const SEVERITY_FILL: Record<string, string> = {
  low: "#3b82f6",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

function ClusterCard({
  cluster,
  selected,
  onClick,
}: {
  cluster: Cluster;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "w-full text-left p-4 rounded-xl border transition-all",
        selected
          ? "bg-sage-500/10 border-sage-500/30"
          : "card-glass hover:bg-slate-800/60"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span
            className="w-2.5 h-2.5 rounded-sm shrink-0 mt-0.5"
            style={{ background: SEVERITY_FILL[cluster.severity] }}
          />
          <span className="text-sm font-medium text-slate-200 truncate">
            {cluster.name}
          </span>
        </div>
        <span
          className={clsx(
            "text-[10px] uppercase px-2 py-0.5 rounded-full border shrink-0",
            SEVERITY_BG[cluster.severity]
          )}
          style={{ color: SEVERITY_FILL[cluster.severity] }}
        >
          {cluster.severity}
        </span>
      </div>

      <div className="flex items-center gap-3 mt-2 pl-4.5">
        <span className="text-[10px] font-mono text-sage-400 bg-sage-500/10 px-2 py-0.5 rounded-md">
          {cluster.log_count} events
        </span>
        <span className="text-[10px] text-slate-500">
          Last: {format(new Date(cluster.last_seen), "HH:mm:ss")}
        </span>
      </div>

      {cluster.tags?.length ? (
        <div className="flex flex-wrap gap-1 mt-2 pl-4.5">
          {cluster.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/50"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </button>
  );
}

function ClusterDetail({ cluster }: { cluster: Cluster }) {
  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span
            className="w-3 h-3 rounded-sm"
            style={{ background: SEVERITY_FILL[cluster.severity] }}
          />
          <h2 className="text-base font-semibold text-slate-100">{cluster.name}</h2>
        </div>
        {cluster.description && (
          <p className="text-xs text-slate-400 leading-relaxed">{cluster.description}</p>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Events", value: cluster.log_count.toLocaleString() },
          {
            label: "First Seen",
            value: format(new Date(cluster.first_seen), "HH:mm:ss"),
          },
          {
            label: "Last Seen",
            value: format(new Date(cluster.last_seen), "HH:mm:ss"),
          },
        ].map((s) => (
          <div key={s.label} className="p-3 rounded-lg bg-slate-800/50 text-center">
            <div className="text-base font-mono font-semibold text-slate-100">
              {s.value}
            </div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Services */}
      {cluster.tags?.length ? (
        <div>
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
            Affected Services
          </div>
          <div className="flex flex-wrap gap-1.5">
            {cluster.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs font-mono px-2 py-1 rounded-md bg-slate-800 text-slate-300 border border-slate-700"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {/* Representative messages */}
      {cluster.representative_messages?.length ? (
        <div>
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
            Representative Messages
          </div>
          <div className="space-y-1.5">
            {cluster.representative_messages.map((msg, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-800/50 border border-slate-700/30"
              >
                <span className="text-[10px] font-mono text-slate-600 shrink-0 mt-0.5">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-xs font-mono text-slate-300 break-all">{msg}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Timeline bar */}
      <div>
        <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
          Activity Window
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              background: `linear-gradient(90deg, ${SEVERITY_FILL[cluster.severity]}40, ${SEVERITY_FILL[cluster.severity]})`,
              width: `${Math.min(100, (cluster.log_count / 50) * 100)}%`,
            }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-slate-600 mt-1 font-mono">
          <span>{format(new Date(cluster.first_seen), "MMM d HH:mm")}</span>
          <span>{format(new Date(cluster.last_seen), "MMM d HH:mm")}</span>
        </div>
      </div>
    </div>
  );
}

export default function ClusterPanel() {
  const { data, isLoading, mutate } = useClusters(30);
  const [selected, setSelected] = useState<Cluster | null>(null);

  const clusters = data?.clusters ?? [];

  return (
    <div className="flex h-full gap-5">
      {/* List */}
      <div className="w-80 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">
            Clusters{" "}
            <span className="text-slate-500 font-mono text-xs">
              ({data?.total ?? 0})
            </span>
          </h2>
          <button
            onClick={() => mutate()}
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {isLoading ? (
            <div className="flex justify-center pt-8">
              <Loader2 className="w-5 h-5 text-sage-400 animate-spin" />
            </div>
          ) : clusters.length === 0 ? (
            <div className="text-xs text-slate-500 text-center pt-8">
              No clusters yet
            </div>
          ) : (
            clusters.map((c) => (
              <ClusterCard
                key={c.id}
                cluster={c}
                selected={selected?.id === c.id}
                onClick={() => setSelected(c)}
              />
            ))
          )}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 card-glass rounded-xl p-5 overflow-y-auto">
        {selected ? (
          <ClusterDetail cluster={selected} />
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-3">
            <Layers className="w-10 h-10 opacity-30" />
            <p className="text-sm">Select a cluster to inspect</p>
          </div>
        )}
      </div>
    </div>
  );
}
