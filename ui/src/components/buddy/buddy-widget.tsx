"use client";

import { useState, useEffect, useCallback } from "react";
import { useBuddyStore, type BuddyMood } from "@/lib/stores/buddy-store";
import { BuddySprite } from "./buddy-sprite";
import { BuddyTips } from "./buddy-tips";
import { cn } from "@/lib/utils/cn";
import {
  Egg,
  Volume2,
  VolumeX,
  RotateCcw,
  ChevronUp,
  ChevronDown,
  Flame,
  Trophy,
  Star,
} from "lucide-react";

const MOOD_EMOJI: Record<BuddyMood, string> = {
  happy: "(◕ᴗ◕✿)",
  curious: "(◕‿◕)?",
  sleepy: "(◡ ᵕ ◡)",
  excited: "(ﾉ◕ヮ◕)ﾉ",
  idle: "(• ᵕ •)",
};

const STAGE_LABEL: Record<number, string> = {
  0: "Egg",
  1: "Hatchling",
  2: "Juvenile",
  3: "Elder",
};

export function BuddyWidget() {
  const store = useBuddyStore();
  const {
    hatched, name, species, personality, mood, muted, lastReaction, totalPets,
    xp, level, xpNext, evolutionStage, streak, achievements,
    hatch, pet, mute, unmute, reset, syncFromBackend,
  } = store;

  const [showReaction, setShowReaction] = useState(false);
  const [expanded, setExpanded] = useState(false);

  /* Reaction bubble auto-hide */
  useEffect(() => {
    if (lastReaction) {
      setShowReaction(true);
      const timer = setTimeout(() => setShowReaction(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [lastReaction]);

  /* Sync from backend on mount */
  const doSync = useCallback(async () => {
    try {
      const res = await fetch("/api/backend/v1/buddy");
      if (!res.ok) return;
      const data = await res.json();
      if (data && typeof data === "object") syncFromBackend(data);
    } catch { /* backend unreachable */ }
  }, [syncFromBackend]);

  useEffect(() => {
    if (hatched) doSync();
  }, [hatched]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---------- Unhatched state ---------- */
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

  const xpPercent = xpNext > 0 ? Math.min(100, Math.round(((xp - (xpNext - xp)) / xpNext) * 100)) : 100;
  // More robust progress: how far between current level threshold and next
  const currentLevelXp = LEVEL_THRESHOLDS[level] ?? 0;
  const nextLevelXp = LEVEL_THRESHOLDS[level + 1] ?? xpNext;
  const progressPct = nextLevelXp > currentLevelXp
    ? Math.min(100, Math.round(((xp - currentLevelXp) / (nextLevelXp - currentLevelXp)) * 100))
    : 100;

  return (
    <div className="border-t border-[var(--chat-border)]">
      {/* === Collapsed header === */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[color:color-mix(in_srgb,var(--chat-accent)_6%,transparent)] transition-colors"
      >
        {/* Sprite avatar */}
        <div
          onClick={(e) => { e.stopPropagation(); pet(); }}
          className="flex-shrink-0 cursor-pointer hover:scale-110 transition-transform"
          title={`Pet ${name}`}
        >
          <BuddySprite species={species} stage={evolutionStage} mood={mood} size={32} />
        </div>

        <div className="flex-1 min-w-0 text-left">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-[var(--chat-accent-strong)] truncate">
              {name}
            </span>
            <span className="text-[10px] text-[var(--chat-muted)]">Lv.{level}</span>
            <span className="text-[10px] text-[var(--chat-muted)]">{MOOD_EMOJI[mood]}</span>
          </div>
          {/* XP progress bar */}
          <div className="w-full h-1.5 mt-0.5 rounded-full bg-[var(--chat-border)] overflow-hidden">
            <div
              className="h-full rounded-full bg-[var(--chat-accent)] transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {streak > 0 && (
          <span className="flex items-center gap-0.5 text-[10px] text-orange-400" title={`${streak} day streak`}>
            <Flame size={10} /> {streak}
          </span>
        )}

        {expanded ? <ChevronDown size={12} className="text-[var(--chat-muted)]" /> : <ChevronUp size={12} className="text-[var(--chat-muted)]" />}
      </button>

      {/* Reaction bubble (always visible) */}
      <div className={cn(
        "px-3 text-[10px] italic text-[var(--chat-accent)] transition-all duration-300 overflow-hidden",
        showReaction && lastReaction ? "max-h-6 opacity-100 pb-1" : "max-h-0 opacity-0"
      )}>
        {lastReaction}
      </div>

      {/* === Expanded panel === */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3 animate-in slide-in-from-bottom-2 duration-200">
          {/* Tip speech bubble */}
          <BuddyTips />

          {/* Sprite large */}
          <div className="flex items-center justify-center py-2">
            <div
              onClick={() => pet()}
              className="cursor-pointer hover:scale-105 transition-transform"
              title={`Pet ${name}`}
            >
              <BuddySprite species={species} stage={evolutionStage} mood={mood} size={64} />
            </div>
          </div>

          {/* Info grid */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <InfoItem label="Species" value={species} />
            <InfoItem label="Stage" value={`${STAGE_LABEL[evolutionStage] ?? "?"} (${evolutionStage}/3)`} />
            <InfoItem label="XP" value={`${xp} / ${nextLevelXp}`} />
            <InfoItem label="Pets" value={String(totalPets)} />
            <InfoItem label="Personality" value={personality} span2 />
          </div>

          {/* Achievements */}
          {achievements.length > 0 && (
            <div>
              <div className="flex items-center gap-1 mb-1 text-[10px] text-[var(--chat-muted)]">
                <Trophy size={10} /> Achievements ({achievements.length})
              </div>
              <div className="flex flex-wrap gap-1">
                {achievements.map((a) => (
                  <span
                    key={a.id}
                    className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] rounded bg-[color:color-mix(in_srgb,var(--chat-accent)_14%,transparent)] text-[var(--chat-accent)]"
                    title={a.description ?? a.name}
                  >
                    <Star size={8} /> {a.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-1 border-t border-[var(--chat-border)]">
            <div className="flex gap-1">
              <button
                onClick={muted ? unmute : mute}
                className="p-1 text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors rounded"
                title={muted ? "Unmute" : "Mute"}
              >
                {muted ? <VolumeX size={12} /> : <Volume2 size={12} />}
              </button>
              <button
                onClick={reset}
                className="p-1 text-[var(--chat-muted)] hover:text-red-400 transition-colors rounded"
                title="Release companion"
              >
                <RotateCcw size={12} />
              </button>
            </div>
            <span className="text-[9px] text-[var(--chat-muted)]">
              {species} · Lv.{level}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/* Helper: info row */
function InfoItem({ label, value, span2 }: { label: string; value: string; span2?: boolean }) {
  return (
    <div className={span2 ? "col-span-2" : ""}>
      <span className="text-[var(--chat-muted)]">{label}: </span>
      <span className="text-[var(--chat-text)]">{value}</span>
    </div>
  );
}

/* Duplicated from store for XP bar calculation */
const LEVEL_THRESHOLDS = [
  0, 10, 20, 50, 100, 200, 350, 550, 800, 1100,
  1500, 2000, 2700, 3600, 4800, 6300, 8200, 10600,
  13700, 17600, 22600,
];
