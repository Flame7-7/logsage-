"use client";

import { useCallback, useState } from "react";
import { Upload, FileText, CheckCircle, Loader2, Zap, AlertTriangle } from "lucide-react";
import { clsx } from "clsx";
import { uploadLogFile, simulateLogs } from "@/lib/api";
import type { IngestionResult } from "@/types";

const SCENARIOS = [
  { id: "mixed", label: "Mixed Logs", desc: "All services, realistic mix" },
  { id: "incident", label: "Incident Scenario", desc: "Discord bot outage chain" },
  { id: "redis", label: "Redis Failures", desc: "Connection timeouts + pool exhaustion" },
  { id: "gateway", label: "Gateway Storm", desc: "Reconnect spike + shard overload" },
  { id: "database", label: "DB Saturation", desc: "Pool exhaustion + slow queries" },
  { id: "worker", label: "Worker Crash", desc: "OOM + task queue backup" },
];

function ResultCard({ result }: { result: IngestionResult }) {
  return (
    <div className="card-glass rounded-xl p-5 border-sage-500/20 border animate-fade-in">
      <div className="flex items-center gap-2 mb-4">
        <CheckCircle className="w-4 h-4 text-sage-400" />
        <span className="text-sm font-semibold text-sage-300">Ingestion Complete</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Processed", value: result.processed_lines.toLocaleString(), color: "text-sage-400" },
          { label: "Incidents", value: result.incidents_detected, color: result.incidents_detected > 0 ? "text-red-400" : "text-slate-400" },
          { label: "Clusters", value: result.clusters_updated, color: "text-blue-400" },
          { label: "Errors", value: result.error_lines, color: result.error_lines > 0 ? "text-yellow-400" : "text-slate-400" },
          { label: "Total Lines", value: result.total_lines.toLocaleString(), color: "text-slate-300" },
          { label: "Time (ms)", value: Math.round(result.processing_time_ms), color: "text-slate-300" },
        ].map((s) => (
          <div key={s.label} className="p-3 rounded-lg bg-slate-800/50 text-center">
            <div className={clsx("text-lg font-mono font-bold", s.color)}>{s.value}</div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 text-[10px] text-slate-600 font-mono">
        Session: {result.session_id}
      </div>
    </div>
  );
}

export default function UploadPanel() {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [simCount, setSimCount] = useState(200);
  const [simScenario, setSimScenario] = useState("mixed");
  const [activeMode, setActiveMode] = useState<"upload" | "simulate">("upload");

  const handleFile = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadLogFile(file);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await simulateLogs(simCount, simScenario);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-100 mb-1">Ingest Logs</h2>
        <p className="text-xs text-slate-500">
          Upload log files or generate realistic sample data for analysis.
        </p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 p-1 bg-slate-800/60 rounded-lg w-fit">
        {(["upload", "simulate"] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setActiveMode(mode)}
            className={clsx(
              "px-4 py-1.5 text-xs rounded-md transition-all capitalize font-medium",
              activeMode === mode
                ? "bg-sage-500/20 text-sage-300 border border-sage-500/30"
                : "text-slate-500 hover:text-slate-300"
            )}
          >
            {mode === "upload" ? "Upload File" : "Simulate"}
          </button>
        ))}
      </div>

      {activeMode === "upload" ? (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          className={clsx(
            "relative border-2 border-dashed rounded-xl p-12 text-center transition-all",
            dragging
              ? "border-sage-400/60 bg-sage-500/5"
              : "border-slate-700/60 hover:border-slate-600",
            loading && "pointer-events-none opacity-60"
          )}
        >
          <input
            type="file"
            accept=".txt,.log,.json,.csv,.ndjson"
            className="absolute inset-0 opacity-0 cursor-pointer"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
          {loading ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 text-sage-400 animate-spin" />
              <p className="text-sm text-slate-400">Processing logs…</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center">
                <Upload className="w-5 h-5 text-slate-400" />
              </div>
              <div>
                <p className="text-sm text-slate-300 font-medium">
                  Drop a log file or click to browse
                </p>
                <p className="text-xs text-slate-600 mt-1">
                  Supports TXT, JSON, CSV, NDJSON · Max 100 MB
                </p>
              </div>
              <div className="flex gap-2 text-[10px] font-mono text-slate-600">
                {[".txt", ".log", ".json", ".csv"].map((ext) => (
                  <span key={ext} className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                    {ext}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="card-glass rounded-xl p-5 space-y-5">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-sage-400" />
            <h3 className="text-sm font-medium text-slate-200">Generate Sample Logs</h3>
          </div>

          {/* Scenario picker */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase tracking-wider block mb-2">
              Scenario
            </label>
            <div className="grid grid-cols-2 gap-2">
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSimScenario(s.id)}
                  className={clsx(
                    "text-left p-3 rounded-lg border text-xs transition-all",
                    simScenario === s.id
                      ? "bg-sage-500/10 border-sage-500/30 text-sage-200"
                      : "bg-slate-800/40 border-slate-700/50 text-slate-400 hover:border-slate-600"
                  )}
                >
                  <div className="font-medium text-slate-200">{s.label}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Count slider */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase tracking-wider block mb-2">
              Log Count: <span className="text-sage-400 font-mono">{simCount}</span>
            </label>
            <input
              type="range"
              min={10}
              max={2000}
              step={10}
              value={simCount}
              onChange={(e) => setSimCount(Number(e.target.value))}
              className="w-full accent-sage-500"
            />
            <div className="flex justify-between text-[10px] text-slate-600 font-mono mt-1">
              <span>10</span>
              <span>2000</span>
            </div>
          </div>

          <button
            onClick={handleSimulate}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 text-sm font-medium bg-sage-600/20 text-sage-300 border border-sage-500/30 rounded-lg hover:bg-sage-600/30 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                Generate &amp; Ingest
              </>
            )}
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Result */}
      {result && <ResultCard result={result} />}

      {/* Supported formats info */}
      {activeMode === "upload" && !result && (
        <div className="p-4 rounded-xl bg-slate-800/30 border border-slate-700/40">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <FileText className="w-3 h-3" />
            Supported Log Formats
          </div>
          <div className="grid grid-cols-3 gap-3 text-xs text-slate-500">
            {[
              { fmt: "Plain Text", eg: "2024-01-01 ERROR redis: timeout" },
              { fmt: "JSON Lines", eg: '{"level":"ERROR","msg":"..."}' },
              { fmt: "CSV", eg: "timestamp,level,service,message" },
            ].map((f) => (
              <div key={f.fmt} className="space-y-1">
                <div className="text-slate-300 font-medium">{f.fmt}</div>
                <div className="font-mono text-[10px] text-slate-600 bg-slate-900/50 px-2 py-1 rounded truncate">
                  {f.eg}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
