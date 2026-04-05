"use client";

import { useEffect, useState } from "react";
import { Bot } from "lucide-react";
import { useSettingsStore, type ChatTheme } from "@/lib/stores/settings-store";

/** Theme-specific thinking phrases that rotate while the model is generating. */
const THINKING_WORDS: Record<ChatTheme, string[]> = {
  hive: [
    "Consulting the hive mind…",
    "Neurons firing…",
    "Weaving synapses…",
    "Assembling swarm knowledge…",
    "Cross-referencing agents…",
  ],
  neon: [
    "Charging circuits…",
    "Scanning data streams…",
    "Decrypting signal…",
    "Routing through the grid…",
    "Amplifying resonance…",
  ],
  ember: [
    "Stoking the forge…",
    "Smelting thoughts…",
    "Igniting pathways…",
    "Tempering the answer…",
    "Fanning the embers…",
  ],
  forest: [
    "Growing new branches…",
    "Listening to the roots…",
    "Photosynthesising ideas…",
    "Tracing the canopy…",
    "Gathering from the grove…",
  ],
};

interface ThinkingIndicatorProps {
  statusMessage: string | null;
  latestThought: string | null;
  streamMode: string;
}

export function ThinkingIndicator({
  statusMessage,
  latestThought,
  streamMode,
}: ThinkingIndicatorProps) {
  const theme = useSettingsStore((s) => s.theme);
  const phrases = THINKING_WORDS[theme] ?? THINKING_WORDS.hive;
  const [phraseIdx, setPhraseIdx] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPhraseIdx((i) => (i + 1) % phrases.length);
    }, 2400);
    return () => clearInterval(interval);
  }, [phrases.length]);

  const displayText = statusMessage ?? latestThought ?? phrases[phraseIdx];

  return (
    <div className="flex gap-3 py-4 px-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-[color:color-mix(in_srgb,var(--chat-thinking)_25%,transparent)] flex items-center justify-center">
        <Bot size={16} className="text-[var(--chat-thinking)]" />
      </div>
      <div className="flex-1 flex items-center gap-3 min-h-[1.75rem]">
        {/* Animated dots */}
        <span className="inline-flex gap-1">
          <span
            className="thinking-dot w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: "var(--chat-thinking)" }}
          />
          <span
            className="thinking-dot w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: "var(--chat-thinking)" }}
          />
          <span
            className="thinking-dot w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: "var(--chat-thinking)" }}
          />
        </span>

        {/* Rotating thinking text */}
        <span
          className="text-sm italic transition-opacity duration-300"
          style={{ color: "var(--chat-thinking)", animation: "thinking-pulse 2.4s ease-in-out infinite" }}
        >
          {displayText}
        </span>

        {streamMode === "thinking" && (
          <span className="ml-auto text-[10px] uppercase tracking-wider text-[var(--chat-muted)]">
            thinking
          </span>
        )}
      </div>
    </div>
  );
}
