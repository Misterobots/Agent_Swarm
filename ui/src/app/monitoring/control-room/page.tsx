import { ShieldCheck } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function ControlRoomPage() {
  return (
    <WorkspaceShell
      title="Control Room"
      description="Protected operations surface for runtime testing and maintenance actions."
      icon={ShieldCheck}
    >
      <WorkspaceSection title="Operational Actions">
        <WorkspacePlaceholder
          title="Protected actions pending"
          body="Reliability tests, restart flows, and maintenance actions from the legacy portal can be moved here once role and approval checks are wired into the Next UI."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}