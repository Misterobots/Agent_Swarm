"use client";

import type { BuddySpecies, EvolutionStage, BuddyMood } from "@/lib/stores/buddy-store";

interface BuddySpriteProps {
  species: BuddySpecies;
  stage: EvolutionStage;
  mood: BuddyMood;
  size?: number;
  className?: string;
}

/**
 * SVG pixel-art sprite for each buddy species.
 * Each species has 4 evolution stages (0-3) with distinct visual variants.
 * Mood affects the color accent and eye shape.
 */
export function BuddySprite({ species, stage, mood, size = 48, className }: BuddySpriteProps) {
  const palette = SPECIES_PALETTES[species] ?? SPECIES_PALETTES["pixel-sprite"];
  const colors = palette[stage] ?? palette[0];
  const eye = MOOD_EYES[mood] ?? MOOD_EYES.idle;
  const accent = MOOD_ACCENT[mood] ?? colors.accent;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      className={className}
      style={{ imageRendering: "pixelated" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Body base */}
      <rect x={4} y={6} width={8} height={7} rx={1} fill={colors.body} />
      {/* Head */}
      <rect x={3} y={2} width={10} height={6} rx={2} fill={colors.body} />
      {/* Eye left */}
      <rect x={5} y={4} width={eye.w} height={eye.h} fill={colors.eye} />
      {/* Eye right */}
      <rect x={9} y={4} width={eye.w} height={eye.h} fill={colors.eye} />
      {/* Mouth */}
      <rect x={7} y={6} width={2} height={1} fill={accent} />
      {/* Species features */}
      {renderSpeciesFeatures(species, stage, colors, accent)}
      {/* Evolution glow */}
      {stage >= 2 && (
        <rect x={2} y={1} width={12} height={14} rx={3} fill={accent} opacity={0.12} />
      )}
      {stage >= 3 && (
        <>
          <rect x={1} y={0} width={1} height={1} fill={accent} opacity={0.4} />
          <rect x={14} y={0} width={1} height={1} fill={accent} opacity={0.4} />
          <rect x={7} y={0} width={2} height={1} fill={accent} opacity={0.3} />
        </>
      )}
    </svg>
  );
}

/* Species-specific decorations */
function renderSpeciesFeatures(
  species: BuddySpecies,
  stage: EvolutionStage,
  colors: { body: string; accent: string; eye: string },
  accent: string,
) {
  switch (species) {
    case "byte-bat":
      return (
        <>
          {/* Ears / wings */}
          <rect x={2} y={2} width={2} height={3} fill={colors.accent} />
          <rect x={12} y={2} width={2} height={3} fill={colors.accent} />
          {stage >= 1 && <rect x={1} y={3} width={1} height={2} fill={colors.accent} />}
          {stage >= 1 && <rect x={14} y={3} width={1} height={2} fill={colors.accent} />}
        </>
      );
    case "data-fox":
      return (
        <>
          {/* Pointy ears */}
          <rect x={3} y={1} width={2} height={2} fill={colors.accent} />
          <rect x={11} y={1} width={2} height={2} fill={colors.accent} />
          {/* Tail */}
          <rect x={11} y={10} width={3} height={2} rx={1} fill={colors.accent} />
          {stage >= 1 && <rect x={13} y={9} width={2} height={2} rx={1} fill={colors.accent} />}
        </>
      );
    case "circuit-cat":
      return (
        <>
          {/* Ears */}
          <rect x={3} y={1} width={2} height={2} fill={colors.body} />
          <rect x={11} y={1} width={2} height={2} fill={colors.body} />
          {/* Whiskers */}
          <rect x={1} y={5} width={3} height={1} fill={colors.accent} opacity={0.5} />
          <rect x={12} y={5} width={3} height={1} fill={colors.accent} opacity={0.5} />
          {stage >= 1 && <rect x={1} y={4} width={2} height={1} fill={colors.accent} opacity={0.3} />}
        </>
      );
    case "logic-lizard":
      return (
        <>
          {/* Tail */}
          <rect x={11} y={12} width={4} height={2} rx={1} fill={colors.accent} />
          {/* Spikes */}
          {stage >= 1 && <rect x={7} y={1} width={2} height={2} fill={colors.accent} />}
          {stage >= 2 && <rect x={5} y={1} width={1} height={1} fill={accent} />}
          {stage >= 2 && <rect x={10} y={1} width={1} height={1} fill={accent} />}
        </>
      );
    case "hash-hamster":
      return (
        <>
          {/* Round cheeks */}
          <rect x={2} y={4} width={2} height={2} rx={1} fill={colors.accent} opacity={0.5} />
          <rect x={12} y={4} width={2} height={2} rx={1} fill={colors.accent} opacity={0.5} />
          {/* Feet */}
          <rect x={5} y={13} width={2} height={1} fill={colors.body} />
          <rect x={9} y={13} width={2} height={1} fill={colors.body} />
        </>
      );
    default: // pixel-sprite
      return (
        <>
          {/* Star sparkle */}
          <rect x={7} y={1} width={2} height={1} fill={accent} />
          {stage >= 1 && <rect x={1} y={7} width={1} height={1} fill={accent} opacity={0.5} />}
          {stage >= 1 && <rect x={14} y={7} width={1} height={1} fill={accent} opacity={0.5} />}
          {stage >= 2 && <rect x={7} y={15} width={2} height={1} fill={accent} opacity={0.4} />}
        </>
      );
  }
}

/* Color palettes per species per evolution stage */
const SPECIES_PALETTES: Record<string, Record<number, { body: string; accent: string; eye: string }>> = {
  "pixel-sprite": {
    0: { body: "#6ec6ff", accent: "#ffe066", eye: "#1a1a2e" },
    1: { body: "#5aaeff", accent: "#ffd633", eye: "#1a1a2e" },
    2: { body: "#3d8cf0", accent: "#ffb800", eye: "#0d0d1a" },
    3: { body: "#2563eb", accent: "#ff9500", eye: "#0d0d1a" },
  },
  "byte-bat": {
    0: { body: "#7c3aed", accent: "#a78bfa", eye: "#fca5a5" },
    1: { body: "#6d28d9", accent: "#8b5cf6", eye: "#fca5a5" },
    2: { body: "#5b21b6", accent: "#7c3aed", eye: "#f87171" },
    3: { body: "#4c1d95", accent: "#6d28d9", eye: "#ef4444" },
  },
  "data-fox": {
    0: { body: "#fb923c", accent: "#fed7aa", eye: "#1e293b" },
    1: { body: "#f97316", accent: "#fdba74", eye: "#1e293b" },
    2: { body: "#ea580c", accent: "#f97316", eye: "#0f172a" },
    3: { body: "#c2410c", accent: "#ea580c", eye: "#0f172a" },
  },
  "circuit-cat": {
    0: { body: "#64748b", accent: "#22d3ee", eye: "#22d3ee" },
    1: { body: "#475569", accent: "#06b6d4", eye: "#06b6d4" },
    2: { body: "#334155", accent: "#0891b2", eye: "#06b6d4" },
    3: { body: "#1e293b", accent: "#0e7490", eye: "#22d3ee" },
  },
  "logic-lizard": {
    0: { body: "#4ade80", accent: "#86efac", eye: "#1a1a2e" },
    1: { body: "#22c55e", accent: "#4ade80", eye: "#1a1a2e" },
    2: { body: "#16a34a", accent: "#22c55e", eye: "#0d0d1a" },
    3: { body: "#15803d", accent: "#16a34a", eye: "#0d0d1a" },
  },
  "hash-hamster": {
    0: { body: "#fbbf24", accent: "#fde68a", eye: "#1e293b" },
    1: { body: "#f59e0b", accent: "#fbbf24", eye: "#1e293b" },
    2: { body: "#d97706", accent: "#f59e0b", eye: "#0f172a" },
    3: { body: "#b45309", accent: "#d97706", eye: "#0f172a" },
  },
};

/* Eye shapes per mood */
const MOOD_EYES: Record<string, { w: number; h: number }> = {
  happy: { w: 2, h: 1 },    // squinted
  curious: { w: 2, h: 2 },  // wide
  sleepy: { w: 2, h: 1 },   // half-closed
  excited: { w: 2, h: 2 },  // wide
  idle: { w: 2, h: 2 },     // normal
};

/* Mood-based accent color overrides */
const MOOD_ACCENT: Record<string, string | null> = {
  happy: null,
  curious: "#a78bfa",
  sleepy: "#94a3b8",
  excited: "#fbbf24",
  idle: null,
};
