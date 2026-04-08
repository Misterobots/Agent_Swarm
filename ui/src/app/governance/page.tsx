import { Gavel } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function GovernancePage() {
  return (
    <WorkspaceShell
      title="Governance"
      description="Approval queues, review workflows, and decision audit surfaces."
      icon={Gavel}
    >
      <WorkspaceSection title="Approval Workflow">
        <WorkspacePlaceholder
          title="Governance route scaffolded"
          body="This is the dedicated route for the approval queue and request review workflow currently implemented in the legacy Streamlit UI."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}