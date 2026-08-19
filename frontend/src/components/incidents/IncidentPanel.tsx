"use client";

import { useState } from "react";
import { format } from "date-fns";
import {
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Loader2,
  RefreshCw,
  Zap,
} from "lucide-react";
import { clsx } from "clsx";
import {
  useIncidents,
  triggerAnalysis,
  updateIncidentStatus,
  SEVERITY_COLORS,
  SEVERITY_BG,
  STATUS_COLORS,
} from "@/lib/api";
import type { Incident, IncidentSeverity } from "@/types";

const SEVERITY_FILL: Record<IncidentSeverity, string> = {
  low: "#3b82f6",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-sage-600 to-sage-400 transition-all"
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-sage-400">
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

function IncidentDetail({
  incident,
  onAnalyze,
  onResolve,
  analyzing,
}: {
  incident: Incident;
  onAnalyze: () => void;
  onResolve: () => void;
  analyzing: boolean;
}) {
  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className="w-3 h-3 rounded-full mt-1 shrink-0"
          style={{ background: SEVERITY_FILL[incident.severity] }}
        />
        <div className="flex-1">
          <h2 className="text-base font-semibold text-slate-100">{incident.title}</h2>
          <div className="flex items-center gap-3 mt-1">
            <span className={clsx("text-xs", STATUS_COLORS[incident.status])}>
              {incident.status.toUpperCase()}
            </span>
            <span className="text-xs text-slate-500">
              {format(new Date(incident.detected_at), "MMM d, HH:mm:ss")}
            </span>
            <span className="text-xs text-slate-500">{incident.log_count} logs</span>
          </div>
        </div>
      </div>

      {/* Services */}
      {incident.affected_services?.length ? (
        <div className="flex flex-wrap gap-2">
          {incident.affected_services.map((s) => (
            <span
              key={s}
              className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700"
            >
              {s}
            </span>
          ))}
        </div>
      ) : null}

      {/* AI Summary */}
      {incident.ai_summary && (
        <div className="p-3 rounded-lg bg-sage-500/5 border border-sage-500/15">
          <div className="text-[10px] text-sage-400 uppercase tracking-wider mb-1.5">
            AI Summary
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">{incident.ai_summary}</p>
          {incident.ai_confidence !== null && (
            <div className="mt-2">
              <ConfidenceBar value={incident.ai_confidence} />
            </div>
          )}
        </div>
      )}

      {/* Root Causes */}
      {incident.root_causes?.length ? (
        <div>
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
            Root Causes
          </div>
          <div className="space-y-2">
            {incident.root_causes.map((rc, i) => (
              <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-800/50">
                <span className="text-[10px] font-mono text-slate-500 mt-0.5 shrink-0">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-slate-200">{rc.cause}</div>
                  {rc.category && (
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      {rc.category}
                    </div>
                  )}
                </div>
                <div className="shrink-0">
                  <ConfidenceBar value={rc.confidence} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Recommended Fixes */}
      {incident.recommended_fixes?.length ? (
        <div>
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
            Recommended Fixes
          </div>
          <div className="space-y-1.5">
            {incident.recommended_fixes.map((fix, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                <CheckCircle className="w-3.5 h-3.5 text-sage-400 mt-0.5 shrink-0" />
                <span>{fix}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Timeline */}
      {incident.timeline?.length ? (
        <div>
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
            Timeline
          </div>
          <div className="space-y-1 border-l border-slate-700 pl-3">
            {incident.timeline.map((ev, i) => (
              <div key={i} className="relative">
                <div className="absolute -left-4 top-1 w-1.5 h-1.5 rounded-full bg-slate-600" />
                <div className="text-[10px] text-slate-500 font-mono">
                  {format(new Date(ev.timestamp), "HH:mm:ss")}
                </div>
                <div className="text-xs text-slate-300">{ev.event}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={onAnalyze}
          disabled={analyzing}
          className="flex items-center gap-1.5 px-3 py-2 text-xs bg-sage-500/15 text-sage-300 border border-sage-500/30 rounded-lg hover:bg-sage-500/25 transition-colors disabled:opacity-50"
        >
          {analyzing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Zap className="w-3.5 h-3.5" />
          )}
          {analyzing ? "Analyzing…" : "Run AI Analysis"}
        </button>

        {incident.status !== "resolved" && (
          <button
            onClick={onResolve}
            className="flex items-center gap-1.5 px-3 py-2 text-xs bg-slate-700/50 text-slate-300 border border-slate-600/50 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            Resolve
          </button>
        )}
      </div>
    </div>
  );
}

export default function IncidentPanel() {
  const { data, isLoading, mutate } = useIncidents({ limit: 50 });
  const [selected, setSelected] = useState<Incident | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  const handleAnalyze = async () => {
    if (!selected) return;
    setAnalyzing(true);
    try {
      await triggerAnalysis(selected.id);
      await mutate();
    } catch (e) {
      console.error(e);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResolve = async () => {
    if (!selected) return;
    try {
      await updateIncidentStatus(selected.id, "resolved");
      await mutate();
      setSelected(null);
    } catch (e) {
      console.error(e);
    }
  };

  const incidents = data?.incidents ?? [];
  const filtered =
    severityFilter === "all"
      ? incidents
      : incidents.filter((i) => i.severity === severityFilter);

  return (
    <div className="flex h-full gap-5">
      {/* List */}
      <div className="w-80 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">
            Incidents{" "}
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

        {/* Severity filter */}
        <div className="flex gap-1.5">
          {["all", "critical", "high", "medium", "low"].map((s) => (
            <button
              key={s}
              onClick={() => setSeverityFilter(s)}
              className={clsx(
                "text-[10px] px-2 py-1 rounded-md border transition-colors capitalize",
                severityFilter === s
                  ? "bg-sage-500/15 border-sage-500/30 text-sage-300"
                  : "border-slate-700 text-slate-500 hover:text-slate-300"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Incident list */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {isLoading ? (
            <div className="flex justify-center pt-8">
              <Loader2 className="w-5 h-5 text-sage-400 animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-xs text-slate-500 text-center pt-8">
              No incidents found
            </div>
          ) : (
            filtered.map((incident) => (
              <button
                key={incident.id}
                onClick={() => setSelected(incident)}
                className={clsx(
                  "w-full text-left p-3 rounded-lg border transition-all",
                  selected?.id === incident.id
                    ? "bg-sage-500/10 border-sage-500/25"
                    : "bg-slate-800/40 border-slate-700/50 hover:bg-slate-800/70"
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: SEVERITY_FILL[incident.severity] }}
                  />
                  <span className="text-xs text-slate-200 truncate flex-1">
                    {incident.title}
                  </span>
                  <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
                </div>
                <div className="flex items-center gap-2 mt-1.5 pl-4">
                  <span className={clsx("text-[10px]", STATUS_COLORS[incident.status])}>
                    {incident.status}
                  </span>
                  <span className="text-[10px] text-slate-600">·</span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {format(new Date(incident.detected_at), "HH:mm:ss")}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 card-glass rounded-xl p-5 overflow-y-auto">
        {selected ? (
          <IncidentDetail
            incident={selected}
            onAnalyze={handleAnalyze}
            onResolve={handleResolve}
            analyzing={analyzing}
          />
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-3">
            <AlertTriangle className="w-10 h-10 opacity-30" />
            <p className="text-sm">Select an incident to view details</p>
          </div>
        )}
      </div>
    </div>
  );
}
