"use client";

import { useServiceHealth } from "@/lib/hooks/use-service-health";
import { ServiceGrid } from "./service-grid";
import { AlertBanner } from "./alert-banner";
import { TrainingStatusPanel } from "./training-status";

/**
 * Headless content block — renders inside MissionControlPage's WorkspaceShell.
 * The page shell owns the title, refresh action, and padding.
 */
export function OpsDashboard() {
  const { health } = useServiceHealth();

  const nodes = health?.nodes || [];
  const controlPlane = health?.control_plane || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <ServiceGrid title="Inference Nodes" nodes={nodes} />
        <ServiceGrid title="Control Plane" services={controlPlane} />
      </div>

      <TrainingStatusPanel />

      <div>
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
          Recent Alerts
        </h3>
        <AlertBanner services={controlPlane} nodes={nodes} />
      </div>
    </div>
  );
}
