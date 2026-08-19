"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Layers,
  Radio,
  Upload,
  Zap,
} from "lucide-react";
import { clsx } from "clsx";

type Tab = "overview" | "incidents" | "clusters" | "live" | "upload";

interface Props {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const NAV_ITEMS: { id: Tab; icon: React.ElementType; label: string }[] = [
  { id: "overview", icon: BarChart3, label: "Overview" },
  { id: "incidents", icon: AlertTriangle, label: "Incidents" },
  { id: "clusters", icon: Layers, label: "Clusters" },
  { id: "live", icon: Radio, label: "Live Feed" },
  { id: "upload", icon: Upload, label: "Ingest Logs" },
];

export default function Sidebar({ activeTab, onTabChange }: Props) {
  return (
    <aside className="w-16 md:w-56 flex flex-col bg-slate-900/80 border-r border-slate-800/60 backdrop-blur-sm shrink-0">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-slate-800/60 gap-3">
        <div className="w-8 h-8 rounded-lg bg-sage-500/20 border border-sage-500/40 flex items-center justify-center shrink-0">
          <Zap className="w-4 h-4 text-sage-400" />
        </div>
        <div className="hidden md:block">
          <div className="text-sm font-semibold text-slate-100">LogSage</div>
          <div className="text-[10px] text-sage-400 font-mono">AI Platform</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV_ITEMS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={clsx(
              "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all",
              activeTab === id
                ? "bg-sage-500/15 text-sage-300 border border-sage-500/25"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            )}
          >
            <Icon className="w-4 h-4 shrink-0" />
            <span className="hidden md:block font-medium">{label}</span>
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-slate-800/60">
        <div className="hidden md:flex items-center gap-2 px-2 py-1.5">
          <Activity className="w-3 h-3 text-sage-400 animate-pulse" />
          <span className="text-[10px] text-slate-500 font-mono">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}
