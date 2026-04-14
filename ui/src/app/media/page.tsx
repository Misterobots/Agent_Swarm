"use client";

import { Image } from "lucide-react";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";
import { fetchComfyStatus, fetchGallery } from "@/lib/api/workspaces";
import { useEffect, useState } from "react";

export default function MediaPage() {
  const [imagesCount, setImagesCount] = useState(0);
  const [audioCount, setAudioCount] = useState(0);
  const [comfyHealthy, setComfyHealthy] = useState(false);

  useEffect(() => {
    Promise.all([fetchGallery("image"), fetchGallery("audio"), fetchComfyStatus()]).then(
      ([images, audio, comfy]) => {
        setImagesCount(images.length);
        setAudioCount(audio.length);
        setComfyHealthy(Boolean(comfy?.healthy));
      }
    );
  }, []);

  return (
    <WorkspaceShell
      title="Media"
      description="Creative generation surfaces for image workflows, 3D conversion, and voice artifacts."
      icon={Image}
    >
      <WorkspaceSection
        title="Creative Surfaces"
        description="Includes Action Figure concept generation and Creature Forge 3D workflows."
      >
        <WorkspaceCardGrid>
          <WorkspaceLinkCard
            title="Images"
            description="Model selection, prompt tuning, and delivered artifact gallery."
            href="/media/images"
          />
          <WorkspaceLinkCard
            title="Action Figure"
            description="Generate action-figure concept renders with model/CFG/sampler controls."
            href="/media/action-figure"
          />
          <WorkspaceLinkCard
            title="Creature Forge"
            description="Convert concept art into 3D assets using TripoSG and Hunyuan Paint workflows."
            href="/media/creature-forge"
          />
          <WorkspaceLinkCard
            title="Voice"
            description="Audio-oriented media workflows and generated voice artifacts."
            href="/media/voice"
          />
        </WorkspaceCardGrid>
      </WorkspaceSection>

      <WorkspaceSection title="Current Library Snapshot">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Image Artifacts</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">{imagesCount}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Audio Artifacts</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">{audioCount}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">ComfyUI</p>
            <p className={`mt-1 text-xl font-semibold ${comfyHealthy ? "text-emerald-400" : "text-red-400"}`}>
              {comfyHealthy ? "Online" : "Offline"}
            </p>
          </div>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
