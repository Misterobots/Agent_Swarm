"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils/cn";
import {
  type SceneCard,
  type SceneJob,
  approveCard,
  composeScene,
  galleryImageUrl,
  pollScene,
  regenerateCard,
} from "@/lib/api/scene";

interface SceneCardGridProps {
  jobId: string;
  onComposite?: (filename: string) => void;
}

const STATUS_BADGE: Record<SceneCard["status"], { text: string; bg: string; border: string; label: string }> = {
  pending:    { text: "text-[var(--chat-muted)]", bg: "bg-[var(--chat-soft)]",   border: "border-[var(--chat-border)]", label: "Queued" },
  generating: { text: "text-[var(--chat-accent)]", bg: "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)]", border: "border-[var(--chat-accent)]", label: "Generating…" },
  ready:      { text: "text-blue-300",   bg: "bg-blue-500/20",    border: "border-blue-500/40",    label: "Ready" },
  approved:   { text: "text-emerald-300", bg: "bg-emerald-500/20", border: "border-emerald-500/40", label: "Approved" },
  rejected:   { text: "text-rose-300",   bg: "bg-rose-500/20",    border: "border-rose-500/40",    label: "Rejected" },
  error:      { text: "text-red-300",    bg: "bg-red-500/20",     border: "border-red-500/40",     label: "Error" },
};

export function SceneCardGrid({ jobId, onComposite }: SceneCardGridProps) {
  const [job, setJob] = useState<SceneJob | null>(null);
  const [composing, setComposing] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let mounted = true;
    pollScene(jobId, (snapshot) => {
      if (mounted) setJob(snapshot);
    }).catch((e) => console.warn("Scene poll ended:", e));
    return () => { mounted = false; };
  }, [jobId]);

  const handleRegenerate = useCallback(async (cardId: string) => {
    try {
      await regenerateCard(jobId, cardId);
      // Poll loop will pick up the state change
    } catch (e) {
      console.error("Regenerate failed:", e);
    }
  }, [jobId]);

  const handleApprove = useCallback(async (cardId: string) => {
    try {
      await approveCard(jobId, cardId);
    } catch (e) {
      console.error("Approve failed:", e);
    }
  }, [jobId]);

  const handleCompose = useCallback(async () => {
    setComposing(true);
    try {
      await composeScene(jobId);
    } catch (e) {
      console.error("Compose failed:", e);
      setComposing(false);
    }
  }, [jobId]);

  if (!job) {
    return (
      <div className="my-2 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4 text-sm text-[var(--chat-muted)]">
        Loading scene…
      </div>
    );
  }

  if (job.state === "decomposing") {
    return (
      <div className="my-2 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="animate-pulse">✨</span>
          <span className="text-[var(--chat-text)]">Decomposing your scene…</span>
        </div>
        <p className="text-[11px] text-[var(--chat-muted)] mt-1">
          Ollama is extracting characters and the establishing shot. ~10-30s.
        </p>
      </div>
    );
  }

  if (job.state === "done" && job.composite_path) {
    onComposite?.(job.composite_path);
    return (
      <div className="my-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4">
        <div className="text-sm font-semibold text-emerald-300 mb-2">Composite ready</div>
        <img
          src={galleryImageUrl(job.composite_path)}
          alt="Final composite"
          className="rounded-md max-w-full"
        />
      </div>
    );
  }

  const allApproved = job.cards.length > 0 && job.cards.every((c) => c.status === "approved");
  const hasErrors = job.cards.some((c) => c.status === "error");

  return (
    <div className="my-2 rounded-lg overflow-hidden border border-[var(--chat-border)] bg-[var(--chat-surface)] text-sm">
      <div className="flex items-center gap-2 px-3 py-2 bg-[var(--chat-panel)] border-b border-[var(--chat-border)]">
        <span className="text-base">🎬</span>
        <span className="font-semibold text-[var(--chat-text)]">
          Scene Composer · {job.cards.length} Card{job.cards.length !== 1 ? "s" : ""}
        </span>
        <span className="ml-auto text-[9px] text-[var(--chat-muted)]">
          {job.state === "composing" ? "compositing…" : allApproved ? "ready to compose" : "review each card"}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 p-3">
        {job.cards.map((card) => {
          const badge = STATUS_BADGE[card.status];
          return (
            <div
              key={card.card_id}
              className={cn(
                "rounded-md border overflow-hidden bg-[var(--chat-panel)]",
                badge.border,
              )}
            >
              <div className="aspect-square bg-black/20 flex items-center justify-center relative">
                {card.image_path ? (
                  <img
                    src={galleryImageUrl(card.image_path)}
                    alt={card.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-[var(--chat-muted)] text-xs">
                    {card.status === "generating" ? "generating…" : "pending"}
                  </span>
                )}
                <span
                  className={cn(
                    "absolute top-1 right-1 text-[9px] px-1.5 py-0.5 rounded-full border",
                    badge.bg, badge.border, badge.text,
                  )}
                >
                  {badge.label}
                </span>
              </div>

              <div className="p-2">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-[11px] font-semibold text-[var(--chat-text)] truncate">
                    {card.role === "establishing_shot" ? "🌆 " : "👤 "}{card.name}
                  </span>
                </div>
                <p className="text-[10px] text-[var(--chat-muted)] leading-snug line-clamp-2">
                  {card.prompt}
                </p>
                {card.error && (
                  <p className="text-[10px] text-red-300 mt-1">{card.error.slice(0, 80)}</p>
                )}

                <div className="flex gap-1 mt-2">
                  <button
                    disabled={card.status === "generating" || card.status === "pending"}
                    onClick={() => handleRegenerate(card.card_id)}
                    className="flex-1 text-[10px] px-2 py-1 rounded border border-[var(--chat-border)] hover:bg-[var(--hover-tint)] disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Regenerate
                  </button>
                  <button
                    disabled={card.status !== "ready"}
                    onClick={() => handleApprove(card.card_id)}
                    className="flex-1 text-[10px] px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Approve
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="px-3 py-2 border-t border-[var(--chat-border)] bg-[var(--chat-panel)] flex items-center justify-between">
        <span className="text-[11px] text-[var(--chat-muted)]">
          {job.cards.filter((c) => c.status === "approved").length}/{job.cards.length} approved
          {hasErrors && <span className="ml-2 text-red-300">· {job.cards.filter((c) => c.status === "error").length} error(s)</span>}
        </span>
        <button
          disabled={!allApproved || composing || job.state === "composing"}
          onClick={handleCompose}
          className="text-[11px] font-semibold px-3 py-1 rounded bg-[var(--chat-accent)] text-black hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {composing || job.state === "composing" ? "Compositing…" : "Compose with OmniGen2"}
        </button>
      </div>
    </div>
  );
}
