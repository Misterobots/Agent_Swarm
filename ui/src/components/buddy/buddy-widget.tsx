"use client";

import { useState, useEffect } from "react";
import { useBuddyStore, type BuddyMood } from "@/lib/stores/buddy-store";
import { cn } from "@/lib/utils/cn";
import { Egg, Volume2, VolumeX, RotateCcw } from "lucide-react";

const MOOD_EMOJI: Record<BuddyMood, string> = {
  happy: "(◕ᴗ◕✿)",
  curious: "(◕‿◕)?",
  sleepy: "(◡ ᵕ ◡)",
  excited: "(ﾉ◕ヮ◕)ﾉ",
  idle: "(• ᵕ •)",
};

const SPECIES_ICON: Record<string, string> = {
  "pixel-sprite": "✦",
  "byte-bat": "🦇",
  "data-fox": "🦊",
  "circuit-cat": "🐱",
  "logic-lizard": "🦎",
  "hash-hamster": "🐹",
};

export function BuddyWidget() {
  const {
    hatched, name, species, personality, mood, muted, lastReaction, totalPets,
    hatch, pet, mute, unmute, reset,
  } = useBuddyStore();
  const [showReaction, setShowReaction] = useState(false);

  useEffect(() => {
    if (lastReaction) {
      setShowReaction(true);
      const timer = setTimeout(() => setShowReaction(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [lastReaction]);

  if (!hatched) {
    return (
      <div className="px-3 py-3 border-t border-[var(--chat-border)]">
        <button
          onClick={hatch}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-accent)] hover:border-[var(--chat-accent)] rounded-lg border border-[var(--chat-border)] border-dashed transition-colors"
        >
          <Egg size={14} />
          Hatch a Companion
        </button>
      </div>
    );
  }

  return (
    <div className="px-3 py-3 border-t border-[var(--chat-border)]">
      {/* Buddy avatar + name */}
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={() => pet()}
          className="flex-shrink-0 w-8 h-8 rounded-lg bg-[color:color-mix(in_srgb,var(--chat-accent)_14%,transparent)] border border-[var(--chat-border)] flex items-center justify-center text-sm hover:scale-110 transition-transform cursor-pointer"
          title={`Pet ${name}`}
        >
          {SPECIES_ICON[species] || "✦"}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-[var(--chat-accent-strong)] truncate">{name}</span>
            <span className="text-[10px] text-[var(--chat-muted)]">{MOOD_EMOJI[mood]}</span>
          </div>
          <p className="text-[10px] text-[var(--chat-muted)] truncate">{personality}</p>
        </div>
        <div className="flex gap-0.5">
          <button
            onClick={muted ? unmute : mute}
            className="p-1 text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            title={muted ? "Unmute" : "Mute"}
          >
            {muted ? <VolumeX size={11} /> : <Volume2 size={11} />}
          </button>
          <button
            onClick={reset}
            className="p-1 text-[var(--chat-muted)] hover:text-red-400 transition-colors"
            title="Release companion"
          >
            <RotateCcw size={11} />
          </button>
        </div>
      </div>

      {/* Reaction bubble */}
      <div className={cn(
        "text-[10px] italic text-[var(--chat-accent)] transition-all duration-300 overflow-hidden",
        showReaction && lastReaction ? "max-h-6 opacity-100" : "max-h-0 opacity-0"
      )}>
        {lastReaction}
      </div>

      {/* Stats */}
      <div className="flex items-center gap-3 text-[9px] text-[var(--chat-muted)] mt-1">
        <span>Pets: {totalPets}</span>
        <span>{species}</span>
      </div>
    </div>
  );
}
