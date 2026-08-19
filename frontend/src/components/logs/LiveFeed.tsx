"use client";

import { useRef, useEffect, useState } from "react";
import { format } from "date-fns";
import { clsx } from "clsx";
import { Radio, Trash2, Pause, Play, AlertOctagon } from "lucide-react";
import { useLiveFeed } from "@/hooks/useLiveFeed";
import { LEVEL_COLORS } from "@/lib/api";
import type { LiveLogEntry } from "@/types";

const LEVEL_BG: Record<string, string> = {
  DEBUG: "text-slate-500",
  INFO: "text-sage-400",
  WARNING: "text-yellow-400 bg-yellow-400/5",
  ERROR: "text-red-400 bg-red-400/5",
  CRITICAL: "text-red-300 bg-red-400/10 font-bold",
};

function LogRow({ entry }: { entry: LiveLogEntry }) {
  return (
    <div
      className={clsx(
        "flex items-start gap-3 px-3 py-1 rounded font-mono text-[11px] hover:bg-slate-800/40 transition-colors group",
        entry.is_anomaly && "border-l-2 border-red-400 pl-2",
        LEVEL_BG[entry.level]?.split(" ").filter((c) => c.startsWith("bg-"))[0] ?? ""
      )}
    >
      {/* Timestamp */}
      <span className="text-slate-600 shrink-0 tabular-nums">
        {format(new Date(entry.timestamp), "HH:mm:ss.SSS")}
      </span>

      {/* Level badge */}
      <span
        className={clsx(
          "shrink-0 w-14 text-center text-[10px] px-1 py-0.5 rounded",
          LEVEL_COLORS[entry.level]
        )}
      >
        {entry.level}
      </span>

      {/* Service */}
      <span className="shrink-0 w-20 text-slate-500 truncate">
        {entry.service ?? "—"}
      </span>

      {/* Message */}
      <span className={clsx("flex-1 min-w-0 break-all", LEVEL_COLORS[entry.level])}>
        {entry.message}
      </span>

      {/* Anomaly indicator */}
      {entry.is_anomaly && (
        <span className="shrink-0 text-red-400 opacity-0 group-hover:opacity-100 transition-opacity">
          <AlertOctagon className="w-3 h-3" />
        </span>
      )}
    </div>
  );
}

export default function LiveFeed() {
  const { entries, connected, clearEntries } = useLiveFeed();
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom unless paused
  useEffect(() => {
    if (!paused && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [entries, paused]);

  const displayed = paused
    ? entries
    : filter
    ? entries.filter(
        (e) =>
          e.message.toLowerCase().includes(filter.toLowerCase()) ||
          (e.service ?? "").toLowerCase().includes(filter.toLowerCase()) ||
          e.level.toLowerCase().includes(filter.toLowerCase())
      )
    : entries;

  const anomalyCount = entries.filter((e) => e.is_anomaly).length;
  const errorCount = entries.filter((e) =>
    ["ERROR", "CRITICAL"].includes(e.level)
  ).length;

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-slate-200">Live Log Feed</h2>
          <span
            className={clsx(
              "flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-full border",
              connected
                ? "text-sage-400 border-sage-500/30 bg-sage-500/10"
                : "text-slate-500 border-slate-700 bg-slate-800/50"
            )}
          >
            <span
              className={clsx(
                "w-1.5 h-1.5 rounded-full",
                connected ? "bg-sage-400 animate-pulse" : "bg-slate-600"
              )}
            />
            {connected ? "CONNECTED" : "RECONNECTING…"}
          </span>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-3 text-[10px] font-mono">
          {anomalyCount > 0 && (
            <span className="text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full border border-red-400/20">
              {anomalyCount} anomalies
            </span>
          )}
          {errorCount > 0 && (
            <span className="text-orange-400">{errorCount} errors</span>
          )}
          <span className="text-slate-500">{entries.length} entries</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by message, service, level…"
          className="flex-1 bg-slate-800/60 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:border-sage-500/50 font-mono"
        />
        <button
          onClick={() => setPaused((p) => !p)}
          className={clsx(
            "flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg border transition-colors",
            paused
              ? "bg-sage-500/15 border-sage-500/30 text-sage-300"
              : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-slate-200"
          )}
        >
          {paused ? (
            <>
              <Play className="w-3.5 h-3.5" /> Resume
            </>
          ) : (
            <>
              <Pause className="w-3.5 h-3.5" /> Pause
            </>
          )}
        </button>
        <button
          onClick={clearEntries}
          className="flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg border border-slate-700/60 bg-slate-800/60 text-slate-400 hover:text-red-400 transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Terminal */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto card-glass rounded-xl p-3 log-terminal"
      >
        {displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
            <Radio className="w-8 h-8 opacity-30" />
            <p className="text-xs">
              {connected
                ? "Waiting for log events…"
                : "Connecting to live feed…"}
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {displayed.map((entry) => (
              <LogRow key={entry.id} entry={entry} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Level legend */}
      <div className="flex items-center gap-4 text-[10px] font-mono text-slate-600">
        {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((l) => (
          <span key={l} className={LEVEL_COLORS[l]}>
            {l}
          </span>
        ))}
        <span className="ml-auto text-slate-700">
          Scroll up to pause · {displayed.length} visible
        </span>
      </div>
    </div>
  );
}
