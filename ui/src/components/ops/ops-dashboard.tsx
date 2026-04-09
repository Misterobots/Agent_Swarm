"use client";

import { useServiceHealth } from "@/lib/hooks/use-service-health";
import { MetricCard } from "./metric-card";
import { ServiceGrid } from "./service-grid";
import { AlertBanner } from "./alert-banner";
import { TrainingStatusPanel } from "./training-status";
import { Activity, Container, Shield, Clock, RefreshCw } from "lucide-react";

export function OpsDashboard() {
  const { health, loading, refresh } = useServiceHealth();

  const nodes = health?.nodes || [];
  const controlPlane = health?.control_plane || [];
  const healthyNodes = nodes.filter((n) => n.healthy).length;
  const healthyServices = controlPlane.filter((s) => s.healthy).length;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-200">Infrastructure Dashboard</h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            {health ? `Status: ${health.status}` : "Loading..."}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="p-2 rounded-lg text-zinc-400 hover:text-cyan-400 hover:bg-zinc-800 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Inference Nodes"
          value={`${healthyNodes}/${nodes.length}`}
          icon={Activity}
          status={healthyNodes === nodes.length ? "ok" : "error"}
        />
        <MetricCard
          label="Control Plane"
          value={`${healthyServices}/${controlPlane.length}`}
          icon={Container}
          status={healthyServices === controlPlane.length ? "ok" : "warn"}
        />
        <MetricCard
          label="Compliance"
          value="92%"
          delta="+4% vs baseline"
          icon={Shield}
          status="ok"
        />
        <MetricCard
          label="Uptime"
          value="99.2%"
          delta="30-day rolling"
          icon={Clock}
          status="ok"
        />
      </div>

      {/* Service Grids */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ServiceGrid title="Inference Nodes" nodes={nodes} />
        <ServiceGrid title="Control Plane" services={controlPlane} />
      </div>

      {/* Training Pipeline */}
      <TrainingStatusPanel />

      {/* Alerts */}
      <div>
        <h2 className="text-sm font-medium text-zinc-400 mb-3">Recent Alerts</h2>
        <AlertBanner services={controlPlane} nodes={nodes} />
      </div>
    </div>
  );
}
