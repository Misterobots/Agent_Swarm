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
                ? "border-zinc-800 bg-[#0a0a14]"
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
                  <span className="text-xs font-medium text-zinc-400">
                    {MODE_LABELS[entry.mode]}
                  </span>
                  {entry.status === "complete" && (
                    <CheckCircle2 size={12} className="text-emerald-500" />
                  )}
                  {entry.status === "error" && (
                    <XCircle size={12} className="text-red-500" />
                  )}
                  <span className="text-[10px] text-zinc-600 ml-auto">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <p className="text-sm text-zinc-300 mb-2">{entry.prompt}</p>

                {entry.result && (
                  <div
                    className={cn(
                      "rounded-lg p-3 text-xs font-mono",
                      entry.status === "complete"
                        ? "bg-zinc-900/50 text-zinc-400"
                        : "bg-red-950/30 text-red-400"
                    )}
                  >
                    {entry.result}
                  </div>
                )}

                {entry.status === "generating" && (
                  <div className="flex items-center gap-2 mt-2">
                    <div className="h-1 flex-1 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full bg-violet-500 rounded-full animate-pulse w-2/3" />
                    </div>
                    <span className="text-[10px] text-zinc-500">Processing...</span>
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
