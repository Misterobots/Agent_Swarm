import { Shield } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function ControlPage() {
  return (
    <WorkspaceShell
      title="Control"
      description="Administrative control surface for runtime operations and managed actions."
      icon={Shield}
    >
      <WorkspaceSection title="Admin Surface">
        <WorkspacePlaceholder
          title="Control workspace scaffolded"
          body="This page reserves the route for the legacy control workspace while the user-facing navigation is restored first."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}