"use client";

import { SlidersHorizontal } from "lucide-react";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";
import { Card } from "@/components/ui";
import { fetchModelCatalog, fetchOpsTrainingRuns } from "@/lib/api/training";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";

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
            title="Launch Run"
            description="Start a new training run: full pipeline, curated, synthetic, or export."
            href="/training/launch"
          />
          <WorkspaceLinkCard
            title="Run History"
            description="View all past training runs, adapter status, and metrics."
            href="/training/runs"
          />
          <WorkspaceLinkCard
            title="Model Catalog"
            description="GRPO, QLoRA, GGUF conversion, and A/B promotion."
            href="/training/models"
          />
          <WorkspaceLinkCard
            title="Voice Calibration"
            description="BMO voice tuning and playback validation."
            href="/training/voice"
          />
        </WorkspaceCardGrid>
      </WorkspaceSection>

      <WorkspaceSection title="Live Training Snapshot">
        <div className="grid gap-3 sm:grid-cols-3">
          <SnapshotTile label="Training Runs" value={runsCount} />
          <SnapshotTile label="Local GGUF Models" value={ggufCount} accent />
          <SnapshotTile label="Ollama Catalog Entries" value={catalogCount} />
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}

function SnapshotTile({ label, value, accent = false }: { label: string; value: number; accent?: boolean }) {
  return (
    <Card padding="md">
      <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--chat-subtle)]">{label}</p>
      <p
        className={cn(
          "mt-2 text-[28px] font-semibold tabular-nums leading-none",
          accent ? "text-[var(--chat-accent)]" : "text-[var(--chat-text)]"
        )}
      >
        {value}
      </p>
    </Card>
  );
}