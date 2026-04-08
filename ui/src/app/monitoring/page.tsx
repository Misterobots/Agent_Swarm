import { Activity, Radar } from "lucide-react";
import { NodeStatus } from "@/components/shared/node-status";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function MonitoringPage() {
  return (
    <WorkspaceShell
      title="Monitoring"
      description="Operations and observability surfaces for the Hive runtime, traces, evidence, and control actions."
      icon={Activity}
    >
      <WorkspaceSection
        title="Cluster Snapshot"
        description="This reuses the existing node health endpoint already consumed by the chat UI."
      >
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4">
          <NodeStatus />
        </div>
      </WorkspaceSection>

      <WorkspaceSection
        title="Monitoring Surfaces"
        description="These pages map directly to the legacy ops dashboard structure."
      >
        <WorkspaceCardGrid>
          <WorkspaceLinkCard
            title="Dashboard"
            description="Infrastructure health, service availability, and recent alerts."
            href="/monitoring/dashboard"
          />
          <WorkspaceLinkCard
            title="Swarm Observer"
            description="Trace feed and Langfuse inspection for agent activity."
            href="/monitoring/swarm-observer"
          />
          <WorkspaceLinkCard
            title="Evidence Locker"
            description="Browse evidence, architecture notes, and operational artifacts."
            href="/monitoring/evidence-locker"
          />
          <WorkspaceLinkCard
            title="Control Room"
            description="Protected maintenance actions and reliability workflows."
            href="/monitoring/control-room"
          />
        </WorkspaceCardGrid>
      </WorkspaceSection>

      <WorkspaceSection title="Implementation Status">
        <WorkspacePlaceholder
          title="Legacy parity in progress"
          body="The legacy Streamlit ops portal is split into multiple subpages here. The route layer is now in place so each surface can be migrated incrementally without losing navigation continuity."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}