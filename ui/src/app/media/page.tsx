import { Image } from "lucide-react";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function MediaPage() {
  return (
    <WorkspaceShell
      title="Media"
      description="Creative generation surfaces for image workflows, galleries, and voice artifacts."
      icon={Image}
    >
      <WorkspaceSection
        title="Creative Surfaces"
        description="This maps the old media workspace into routeable sections."
      >
        <WorkspaceCardGrid>
          <WorkspaceLinkCard
            title="Images"
            description="Model selection, prompt tuning, and delivered artifact gallery."
            href="/media/images"
          />
          <WorkspaceLinkCard
            title="Voice"
            description="Audio-oriented media workflows and generated voice artifacts."
            href="/media/voice"
          />
        </WorkspaceCardGrid>
      </WorkspaceSection>

      <WorkspaceSection title="Implementation Status">
        <WorkspacePlaceholder
          title="Gallery migration pending"
          body="The image generation controls and gallery from render_media_workspace() now have a dedicated landing route and subsection routes to target during migration."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}