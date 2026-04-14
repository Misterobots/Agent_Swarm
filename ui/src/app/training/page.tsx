"use client";

import { SlidersHorizontal } from "lucide-react";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";
import { fetchModelCatalog, fetchOpsTrainingRuns } from "@/lib/api/training";
import { useEffect, useState } from "react";

export default function TrainingPage() {
  const [runsCount, setRunsCount] = useState(0);
  const [ggufCount, setGgufCount] = useState(0);
  const [catalogCount, setCatalogCount] = useState(0);

  useEffect(() => {
    Promise.all([fetchOpsTrainingRuns(), fetchModelCatalog()]).then(([runs, catalog]) => {
      setRunsCount(runs.length);
      setGgufCount(catalog.local_gguf.length);
      setCatalogCount(catalog.ollama_models.length);
    }).catch((err) => {
      console.error("[Training] Failed to load training data:", err);
    });
  }, []);

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

      <WorkspaceSection title="Live Training Snapshot">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Training Runs</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">{runsCount}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Local GGUF Models</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-accent)]">{ggufCount}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Ollama Catalog Entries</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">{catalogCount}</p>
          </div>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}