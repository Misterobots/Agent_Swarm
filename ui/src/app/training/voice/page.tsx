import { AudioWaveform } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function TrainingVoicePage() {
  return (
    <WorkspaceShell
      title="Voice Calibration"
      description="Calibration surface for BMO voice tuning, playback tests, and inference adjustments."
      icon={AudioWaveform}
    >
      <WorkspaceSection title="Calibration Workspace">
        <WorkspacePlaceholder
          title="BMO tuning surface pending"
          body="This route is the new home for the AI Tuning Studio voice controls currently implemented in agents/ops_dashboard.py."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}