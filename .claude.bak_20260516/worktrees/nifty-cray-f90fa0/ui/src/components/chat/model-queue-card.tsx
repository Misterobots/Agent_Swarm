"use client";

import { useState, useEffect } from "react";

export interface QueueStatusPayload {
  model: string;
  tier: "small" | "large";
  is_loaded: boolean;
  queue_position: number;
  estimated_wait_s: number;
  alternatives: Array<{ name: string; description: string; vram_gb: number }>;
  should_prompt: boolean;
}

interface ModelQueueCardProps {
  status: QueueStatusPayload;
  onUseAlternative?: (modelName: string) => void;
  onDismiss?: () => void;
}

/** Countdown timer that ticks down from initialSeconds */
function Countdown({ initialSeconds }: { initialSeconds: number }) {
  const [remaining, setRemaining] = useState(initialSeconds);

  useEffect(() => {
    if (remaining <= 0) return;
    const id = setInterval(() => setRemaining((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [remaining]);

  if (remaining <= 0) return <span className="text-emerald-400">ready</span>;

  const m = Math.floor(remaining / 60);
  const s = remaining % 60;
  const display = m > 0 ? `${m}m ${s}s` : `${s}s`;
  return <span className="tabular-nums text-amber-300">{display}</span>;
}

export function ModelQueueCard({ status, onUseAlternative, onDismiss }: ModelQueueCardProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  const positionLabel =
    status.queue_position === 0
      ? "Loading model into VRAM…"
      : `Queue position: ${status.queue_position}`;

  return (
    <div className="my-2 rounded-lg border border-amber-700/40 bg-amber-950/20 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-amber-700/30 px-3 py-2">
        <div className="flex items-center gap-2">
          {/* Spinner */}
          <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-amber-400 border-t-transparent" />
          <span className="font-medium text-amber-200">Model Loading</span>
          <span className="rounded bg-amber-900/50 px-1.5 py-0.5 text-xs font-mono text-amber-300/80">
            {status.model}
          </span>
        </div>
        <button
          onClick={handleDismiss}
          className="text-amber-500/60 transition-colors hover:text-amber-400"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5 space-y-2">
        <div className="flex items-center justify-between text-amber-200/80">
          <span>{positionLabel}</span>
          <span className="text-xs">
            Est. wait: <Countdown initialSeconds={status.estimated_wait_s} />
          </span>
        </div>

        {/* VRAM info */}
        <p className="text-xs text-amber-300/50">
          {status.is_loaded
            ? "Model is resident in VRAM — waiting for prior requests to finish."
            : `Model is on disk. Loading ~${status.estimated_wait_s}s to VRAM (20 GB).`}
        </p>

        {/* Alternative suggestion */}
        {status.should_prompt && status.alternatives.length > 0 && (
          <div className="mt-1.5 rounded-md border border-amber-700/30 bg-amber-900/20 px-3 py-2">
            <p className="mb-1.5 text-xs font-medium text-amber-200">
              A faster option is already in VRAM:
            </p>
            <div className="flex flex-wrap gap-2">
              {status.alternatives.map((alt) => (
                <button
                  key={alt.name}
                  onClick={() => onUseAlternative?.(alt.name)}
                  className="flex items-center gap-1.5 rounded-md border border-amber-600/40 bg-amber-900/30 px-2.5 py-1 text-xs text-amber-200 transition-colors hover:border-amber-500 hover:bg-amber-900/50 hover:text-amber-100"
                  title={alt.description}
                >
                  <span className="font-mono">{alt.name}</span>
                  <span className="text-amber-400/60">·</span>
                  <span className="text-amber-300/60">{alt.vram_gb} GB</span>
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-amber-300/40">
              Or wait for <span className="font-mono text-amber-300/60">{status.model}</span> to load.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
