import { Archive } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function EvidenceLockerPage() {
  return (
    <WorkspaceShell
      title="Evidence Locker"
      description="Operational documents, evidence bundles, specs, and compliance artifacts."
      icon={Archive}
    >
      <WorkspaceSection title="Document Browser">
        <WorkspacePlaceholder
          title="Directory-backed evidence view pending"
          body="The legacy folder browser for docs/specs/evidence/compliance/architecture can be migrated onto this page without changing the new route structure."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}