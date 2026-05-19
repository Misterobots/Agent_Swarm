"use client";

import { Gavel } from "lucide-react";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { GovernanceWorkflow } from "@/components/governance/governance-workflow";

export default function GovernancePage() {
  return (
    <WorkspaceShell
      title="Governance"
      description="Approval queues, review workflows, and decision audit surfaces."
      icon={Gavel}
    >
      <GovernanceWorkflow />
    </WorkspaceShell>
  );
}
