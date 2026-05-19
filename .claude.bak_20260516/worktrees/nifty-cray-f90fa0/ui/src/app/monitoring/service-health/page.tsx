"use client";

import { HeartPulse } from "lucide-react";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { ServiceHealthBody } from "@/components/monitoring/service-health-body";

export default function ServiceHealthPage() {
  return (
    <WorkspaceShell
      title="Service Health"
      description="Deep connectivity checks across all cluster services. Restart individual containers when needed."
      icon={HeartPulse}
    >
      <ServiceHealthBody />
    </WorkspaceShell>
  );
}
