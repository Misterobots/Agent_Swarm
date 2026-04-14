"use client";

import { useArtStore } from "@/lib/stores/art-store";
import { Download, Image, Box, Bone, Clock } from "lucide-react";

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

export function ArtExports() {
  const { history } = useArtStore();
  const completed = history.filter((e) => e.status === "complete");

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-sm font-semibold text-[var(--chat-text)] mb-6">Generation Log</h2>

        {completed.length === 0 ? (
          <div className="text-center py-20">
            <Download size={32} className="mx-auto text-[var(--chat-muted)] mb-3" />
            <p className="text-[var(--chat-muted)] text-sm">No completed generations yet.</p>
            <p className="text-[var(--chat-muted)] text-xs mt-1">
              Head to the Generate tab to create images, 3D models, or action figures.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {completed.map((entry) => {
              const Icon = MODE_ICONS[entry.mode];
              return (
                <div
                  key={entry.id}
                  className="flex items-center gap-4 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4"
                >
                  <div className="w-9 h-9 rounded-lg bg-[var(--chat-panel)] flex items-center justify-center flex-shrink-0">
                    <Icon size={18} className="text-[var(--chat-muted)]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[var(--chat-text)] truncate">{entry.prompt}</p>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-[10px] text-[var(--chat-muted)]">
                        {MODE_LABELS[entry.mode]}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] text-[var(--chat-muted)]">
                        <Clock size={8} />
                        {new Date(entry.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  {entry.result && (
                    <span className="text-xs text-[var(--chat-muted)] max-w-[200px] truncate">
                      {entry.result}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
