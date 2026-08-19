"use client";

import { X, AlertOctagon } from "lucide-react";
import { useState } from "react";
import { useAlerts } from "@/lib/api";

export default function AlertBanner() {
  const { data } = useAlerts();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const firing = data?.alerts.filter(
    (a) => a.status === "firing" && !dismissed.has(a.id)
  ) ?? [];

  if (!firing.length) return null;

  const top = firing[0];

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-red-500/10 border-b border-red-500/30 animate-fade-in">
      <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
      <div className="flex-1 min-w-0">
        <span className="text-xs font-semibold text-red-300">{top.title}</span>
        <span className="text-xs text-red-400/70 ml-2">{top.message}</span>
      </div>
      {firing.length > 1 && (
        <span className="text-[10px] text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full border border-red-400/20 shrink-0">
          +{firing.length - 1} more
        </span>
      )}
      <button
        onClick={() => setDismissed((s) => new Set([...s, top.id]))}
        className="shrink-0 text-red-400/60 hover:text-red-400 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
