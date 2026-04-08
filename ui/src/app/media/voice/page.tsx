import { Mic2 } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function MediaVoicePage() {
  return (
    <WorkspaceShell
      title="Media Voice"
      description="Voice artifact generation and media-oriented audio workflows."
      icon={Mic2}
    >
      <WorkspaceSection title="Voice Artifact Surface">
        <WorkspacePlaceholder
          title="Audio generation migration pending"
          body="Use this route if you want generated audio and creative voice artifacts grouped under Media instead of Training."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}