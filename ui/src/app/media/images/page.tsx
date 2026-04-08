import { ImagePlus } from "lucide-react";
import {
  WorkspacePlaceholder,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";

export default function MediaImagesPage() {
  return (
    <WorkspaceShell
      title="Media Images"
      description="Image generation controls and delivered artifact gallery."
      icon={ImagePlus}
    >
      <WorkspaceSection title="Generator Scaffold">
        <WorkspacePlaceholder
          title="Image workflow entrypoint ready"
          body="This route is intended for the checkpoint picker, CFG and sampler controls, and artifact gallery currently implemented in agents/ui.py."
        />
      </WorkspaceSection>
    </WorkspaceShell>
  );
}