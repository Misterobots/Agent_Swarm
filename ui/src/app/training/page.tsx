import { SlidersHorizontal } from "lucide-react";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function TrainingPage() {
  return (
    <WorkspaceShell
      title="Training"
      description="Model tuning, voice calibration, training runs, and promotion workflows."
      icon={SlidersHorizontal}
    >
      <WorkspaceSection
        title="Training Surfaces"
        description="This consolidates legacy AI Tuning Studio and backend training workflows under one top-level label."
      >
        <WorkspaceCardGrid>
          <WorkspaceLinkCard
            title="Voice Calibration"
            description="BMO voice tuning and playback validation."
            href="/training/voice"
          />
          <WorkspaceLinkCard
            title="Model Training"
            description="GRPO, QLoRA, GGUF conversion, and A/B promotion."
            href="/training/models"
          />
        </WorkspaceCardGrid>
      </WorkspaceSection>

      <WorkspaceSection title="Implementation Status">
        <WorkspacePlaceholder
          title="Training routes are live"
          body="The navigation gap is closed. These pages can now absorb training metrics, run history, and voice tuning UIs without inventing a second routing model."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}