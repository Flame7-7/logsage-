"use client";

import { useState } from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import MetricsBar from "@/components/dashboard/MetricsBar";
import IncidentPanel from "@/components/incidents/IncidentPanel";
import ClusterPanel from "@/components/incidents/ClusterPanel";
import LiveFeed from "@/components/logs/LiveFeed";
import UploadPanel from "@/components/logs/UploadPanel";
import AlertBanner from "@/components/dashboard/AlertBanner";
import ChartsPanel from "@/components/dashboard/ChartsPanel";

type Tab = "overview" | "incidents" | "clusters" | "live" | "upload";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  return (
    <div className="flex h-screen overflow-hidden bg-grid">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top alert banner */}
        <AlertBanner />

        {/* Metrics bar */}
        <MetricsBar />

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          {activeTab === "overview" && <ChartsPanel />}
          {activeTab === "incidents" && <IncidentPanel />}
          {activeTab === "clusters" && <ClusterPanel />}
          {activeTab === "live" && <LiveFeed />}
          {activeTab === "upload" && <UploadPanel />}
        </main>
      </div>
    </div>
  );
}
