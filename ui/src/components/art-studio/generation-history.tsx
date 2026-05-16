"use client";

import type { GenerationEntry } from "@/lib/stores/art-store";
import { Image, Box, Bone, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const MODE_ICONS = {
  image: Image,
  "3d": Box,
  "action-figure": Bone,
};

const MODE_LABELS = {
  image: "Image",
  "3d": "3D Model",
  "action-figure": "Action Figure",
};

export function GenerationHistory({ entries }: { entries: GenerationEntry[] }) {
  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {entries.map((entry) => {
        const Icon = MODE_ICONS[entry.mode];
        return (
          <div
            key={entry.id}
            className={cn(
              "rounded-xl border p-4 transition-all",
              entry.status === "generating"
                ? "border-violet-700/50 bg-violet-950/20"
                : entry.status === "complete"
                ? "border-[var(--chat-border)] bg-[var(--chat-bg)]"
                : "border-red-900/50 bg-red-950/10"
            )}
          >
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  "flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center",
                  entry.status === "generating"
                    ? "bg-violet-900/40"
                    : entry.status === "complete"
                    ? "bg-emerald-900/30"
                    : "bg-red-900/30"
                )}
              >
                {entry.status === "generating" ? (
                  <Loader2 size={20} className="text-violet-400 animate-spin" />
                ) : (
                  <Icon
                    size={20}
                    className={entry.status === "complete" ? "text-emerald-400" : "text-red-400"}
                  />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-[var(--chat-muted)]">
                    {MODE_LABELS[entry.mode]}
                  </span>
                  {entry.status === "complete" && (
                    <CheckCircle2 size={12} className="text-emerald-500" />
                  )}
                  {entry.status === "error" && (
                    <XCircle size={12} className="text-red-500" />
                  )}
                  <span className="text-[10px] text-[var(--chat-muted)] ml-auto">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <p className="text-sm text-[var(--chat-text)] mb-2">{entry.prompt}</p>

                {entry.result && (() => {
                  const imgMatch = entry.mode === "image" && entry.status === "complete"
                    ? entry.result.match(/Generated Image: ([\w.\-]+)/)
                    : null;
                  const filename = imgMatch?.[1];
                  if (filename) {
                    return (
                      <div className="rounded-lg overflow-hidden mt-1">
                        <img
                          src={`/api/backend/v1/art/gallery/images/${filename}`}
                          alt={entry.prompt}
                          className="w-full rounded-lg object-cover max-h-96"
                        />
                        <p className="text-[10px] text-[var(--chat-muted)] mt-1 font-mono">{filename}</p>
                      </div>
                    );
                  }
                  return (
                    <div
                      className={cn(
                        "rounded-lg p-3 text-xs font-mono",
                        entry.status === "complete"
                          ? "bg-[var(--chat-panel)] text-[var(--chat-muted)]"
                          : "bg-red-950/30 text-red-400"
                      )}
                    >
                      {entry.result}
                    </div>
                  );
                })()}

                {entry.status === "generating" && (
                  <div className="flex items-center gap-2 mt-2">
                    <div className="h-1 flex-1 bg-[var(--chat-surface)] rounded-full overflow-hidden">
                      <div className="h-full bg-violet-500 rounded-full animate-pulse w-2/3" />
                    </div>
                    <span className="text-[10px] text-[var(--chat-muted)]">Processing...</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
