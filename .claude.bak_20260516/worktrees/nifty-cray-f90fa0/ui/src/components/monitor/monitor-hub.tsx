"use client";

import { useState } from "react";
import { useMonitorStore } from "@/lib/stores/monitor-store";
import { DashboardSelector, DASHBOARDS } from "./dashboard-selector";
import { ExternalLink, Loader2 } from "lucide-react";

// Grafana is loaded directly via the /grafana sub-path.  Traefik routes
// /grafana on both LAN and external domains straight to the Grafana
// container, preserving Grafana's SPA client-side routing.
const GRAFANA_PROXY = "/grafana";

// External link for "Open full Grafana" (direct access outside the iframe)
const GRAFANA_DIRECT = "http://192.168.2.103:3001/grafana";

function useGrafanaBase() {
  return GRAFANA_PROXY;
}

function useGrafanaDirect() {
  if (typeof window === "undefined") return GRAFANA_DIRECT;
  const host = window.location.hostname;
  if (host.endsWith("shivelymedia.com"))
    return "https://grafana.shivelymedia.com/grafana";
  return GRAFANA_DIRECT;
}

export function MonitorHub() {
  const { activeDashboard, setActiveDashboard } = useMonitorStore();
  const [loading, setLoading] = useState(true);
  const grafanaBase = useGrafanaBase();
  const grafanaDirect = useGrafanaDirect();

  const activeLabel = DASHBOARDS.find((d) => d.uid === activeDashboard)?.label || "Dashboard";
  const iframeSrc = `${grafanaBase}/d/${activeDashboard}?orgId=1&kiosk`;
  const fullUrl = `${grafanaDirect}/d/${activeDashboard}?orgId=1`;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
        <DashboardSelector active={activeDashboard} onSelect={(uid) => {
          setActiveDashboard(uid);
          setLoading(true);
        }} />
        <a
          href={fullUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors"
        >
          Open full Grafana
          <ExternalLink size={12} />
        </a>
      </div>

      {/* Grafana iframe */}
      <div className="relative flex-1">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[var(--chat-bg)]">
            <div className="flex flex-col items-center gap-3">
              <Loader2 size={24} className="text-[var(--chat-accent)] animate-spin" />
              <span className="text-sm text-[var(--chat-muted)]">Loading {activeLabel}...</span>
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
