"use client";

import { useState } from "react";
import { useMonitorStore } from "@/lib/stores/monitor-store";
import { DashboardSelector, DASHBOARDS } from "./dashboard-selector";
import { ExternalLink, Loader2 } from "lucide-react";

// Iframe always uses the server-side proxy so Grafana works from any origin
// (LAN or external via Cloudflare). The proxy route forwards to the real
// Grafana instance on the LAN.
const GRAFANA_IFRAME = "/api/grafana";

// "Open full Grafana" link — only works on LAN, but useful as a fallback.
const GRAFANA_DIRECT = process.env.NEXT_PUBLIC_GRAFANA_URL || "http://192.168.2.103/grafana";

export function MonitorHub() {
  const { activeDashboard, setActiveDashboard } = useMonitorStore();
  const [loading, setLoading] = useState(true);

  const activeLabel = DASHBOARDS.find((d) => d.uid === activeDashboard)?.label || "Dashboard";
  const iframeSrc = `${GRAFANA_IFRAME}/d/${activeDashboard}?orgId=1&kiosk`;
  const fullUrl = `${GRAFANA_DIRECT}/d/${activeDashboard}?orgId=1`;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-[#0a0a14]">
        <DashboardSelector active={activeDashboard} onSelect={(uid) => {
          setActiveDashboard(uid);
          setLoading(true);
        }} />
        <a
          href={fullUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-500 hover:text-cyan-400 transition-colors"
        >
          Open full Grafana
          <ExternalLink size={12} />
        </a>
      </div>

      {/* Grafana iframe */}
      <div className="relative flex-1">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a14]">
            <div className="flex flex-col items-center gap-3">
              <Loader2 size={24} className="text-cyan-400 animate-spin" />
              <span className="text-sm text-zinc-500">Loading {activeLabel}...</span>
            </div>
          </div>
        )}
        <iframe
          key={activeDashboard}
          src={iframeSrc}
          title={activeLabel}
          className="w-full h-full border-0"
          style={{ height: "calc(100vh - 6.5rem)" }}
          onLoad={() => setLoading(false)}
        />
      </div>
    </div>
  );
}
