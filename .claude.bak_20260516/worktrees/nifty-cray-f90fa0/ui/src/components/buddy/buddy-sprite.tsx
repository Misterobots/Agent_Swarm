"use client";

import type { BuddySpecies, EvolutionStage, BuddyMood } from "@/lib/stores/buddy-store";

interface BuddySpriteProps {
  species: BuddySpecies;
  stage: EvolutionStage;
  mood: BuddyMood;
  size?: number;
  className?: string;
  /** If true, plays the evolution shimmer animation */
  evolving?: boolean;
}

/**
 * SVG pixel-art sprite for each buddy species.
 * 48×48 viewBox — late 80s / early SNES pixel-art style.
 * Each species has 5 evolution stages (0-4) with distinct visual variants.
 * Mood affects eye shape, mouth, and blush marks.
 */
export function BuddySprite({ species, stage, mood, size = 48, className, evolving = false }: BuddySpriteProps) {
  const palette = SPECIES_PALETTES[species] ?? SPECIES_PALETTES["pixel-sprite"];
  const colors = palette[stage] ?? palette[0];
  const eyes = MOOD_EYES[mood] ?? MOOD_EYES.idle;
  const accent = MOOD_ACCENT[mood] ?? colors.accent;
  const uid = `${species}-${stage}-${mood}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      className={className}
      style={{ imageRendering: "pixelated" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Highlight gradient for body sheen */}
        <linearGradient id={`bodyGrad-${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={colors.highlight} stopOpacity="0.7" />
          <stop offset="100%" stopColor={colors.shadow} stopOpacity="0.4" />
        </linearGradient>
        {evolving && (
          <radialGradient id={`evoGlow-${uid}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={accent} stopOpacity="0.8">
              <animate attributeName="stopOpacity" values="0.8;0.2;0.8" dur="0.6s" repeatCount="3" />
            </stop>
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </radialGradient>
        )}
      </defs>

      {/* ── Body ── */}
      {renderBody(species, stage, colors, uid)}

      {/* ── Face ── */}
      {renderFace(species, stage, colors, eyes, accent, mood)}

      {/* ── Species features ── */}
      {renderSpeciesFeatures(species, stage, colors, accent)}

      {/* ── Evolution overlay: stage 2+ inner glow ── */}
      {stage >= 2 && (
        <rect x={6} y={4} width={36} height={40} rx={8} fill={accent} opacity={0.07} />
      )}

      {/* ── Stage 3+ sparkle pixels ── */}
      {stage >= 3 && SPARKLE_POS.map((p, i) => (
        <rect key={i} x={p[0]} y={p[1]} width={2} height={2} fill={accent} opacity={0.55}>
          <animate attributeName="opacity" values="0.55;0.1;0.55" dur={`${1.2 + i * 0.3}s`} repeatCount="indefinite" />
        </rect>
      ))}

      {/* ── Stage 4 legendary crown + halo ── */}
      {stage >= 4 && renderLegendaryCrown(colors, accent)}

      {/* ── Evolution flash ── */}
      {evolving && (
        <rect x={0} y={0} width={48} height={48} fill={`url(#evoGlow-${uid})`} rx={8} />
      )}
    </svg>
  );
}

/* ─────────────────────────────────────────────── helpers ── */

function renderBody(
  species: BuddySpecies,
  stage: EvolutionStage,
  colors: ColorSet,
  uid: string,
) {
  // ── BMO: arcade-style pixel-art console ───────────────────────────
  if (species === "bmo") {
    return (
      <>
        {/* ─ 1px dark outline behind the whole console ─ */}
        <rect x={8} y={2} width={32} height={41} rx={2} fill={colors.shadow} opacity={0.9} />
        {/* ─ Main console body ─ hard-edge, no rx */}
        <rect x={9} y={3} width={30} height={39} fill={colors.body} />
        {/* Top specular strip */}
        <rect x={10} y={4} width={28} height={3} fill={colors.highlight} opacity={0.55} />
        {/* Left-edge light strip */}
        <rect x={10} y={7} width={2} height={33} fill={colors.highlight} opacity={0.22} />
        {/* Bottom shadow strip */}
        <rect x={10} y={40} width={28} height={2} fill={colors.shadow} opacity={0.45} />
        {/* ─ Screen bezel — 1px shadow-color border ─ */}
        <rect x={11} y={7} width={26} height={20} fill={colors.shadow} />
        {/* ─ Screen interior — pale mint (light, like the real BMO) ─ */}
        <rect x={12} y={8} width={24} height={18} fill="#cde8d8" />
        {/* Pixel corner cuts — bevel without rx */}
        <rect x={12} y={8} width={1} height={1} fill={colors.body} />
        <rect x={35} y={8} width={1} height={1} fill={colors.body} />
        <rect x={12} y={25} width={1} height={1} fill={colors.body} />
        <rect x={35} y={25} width={1} height={1} fill={colors.body} />
        {/* Screen subtle top-sheen on light surface */}
        <rect x={13} y={9} width={22} height={3} fill="#ffffff" opacity={0.28} />
      </>
    );
  }

  // Body grows and gains shading per stage
  const bodyW = 20 + stage * 2;
  const bodyH = 18 + stage * 2;
  const bodyX = (48 - bodyW) / 2;
  const bodyY = 26;

  const headW = 22 + stage * 2;
  const headH = 16 + stage * 2;
  const headX = (48 - headW) / 2;
  const headY = 10;

  return (
    <>
      {/* Shadow / depth pixel row */}
      <rect x={bodyX + 2} y={bodyY + bodyH - 1} width={bodyW - 4} height={2} fill={colors.shadow} opacity={0.5} />
      {/* Body */}
      <rect x={bodyX} y={bodyY} width={bodyW} height={bodyH} rx={4} fill={colors.body} />
      {/* Body highlight strip */}
      <rect x={bodyX + 2} y={bodyY + 1} width={bodyW - 4} height={3} fill={colors.highlight} opacity={0.45} />
      {/* Head */}
      <rect x={headX} y={headY} width={headW} height={headH} rx={5} fill={colors.body} />
      {/* Head highlight */}
      <rect x={headX + 3} y={headY + 1} width={headW - 8} height={3} fill={colors.highlight} opacity={0.5} />
      {/* Neck connector */}
      <rect x={bodyX + 4} y={headY + headH - 2} width={bodyW - 8} height={4} fill={colors.body} />
    </>
  );
}

interface EyeDef { w: number; h: number; shape: "normal" | "happy" | "sleepy" | "star" }

function renderFace(
  species: BuddySpecies,
  stage: EvolutionStage,
  colors: ColorSet,
  eyes: EyeDef,
  accent: string,
  mood: BuddyMood,
) {
  // ── BMO: face on pale-mint screen — black features, light background ─────────────
  // Screen interior: x=12–35, y=8–25 (24×18 px). Center x=23.5
  // Layout: eyes y=10–14 | gap | mouth y=18–22
  if (species === "bmo") {
    // Mood affects eye shape: sleepy = squint (h=2), else full oval (h=5)
    const eyeH = mood === "sleepy" ? 2 : 5;
    const eyeY = mood === "sleepy" ? 12 : 10; // vertically centre squint
    return (
      <>
        {/* Left eye — solid black oval, no whites */}
        <rect x={16} y={eyeY} width={4} height={eyeH} rx={2} fill="#0a1010" />
        {/* Right eye */}
        <rect x={27} y={eyeY} width={4} height={eyeH} rx={2} fill="#0a1010" />
        {/* Mouth — black pixel shapes, mood-responsive */}
        {(mood === "happy" || mood === "excited") ? (
          <>
            {/* U-smile: two side posts + bottom bar */}
            <rect x={17} y={18} width={2} height={3} fill="#0a1010" />
            <rect x={29} y={18} width={2} height={3} fill="#0a1010" />
            <rect x={19} y={21} width={10} height={2} fill="#0a1010" />
          </>
        ) : mood === "sleepy" ? (
          /* flat line, slightly right of centre — drowsy */
          <rect x={20} y={21} width={8} height={1} fill="#0a1010" opacity={0.7} />
        ) : mood === "curious" ? (
          <>
            {/* flat base + right corner flicked up = quizzical look */}
            <rect x={19} y={21} width={10} height={1} fill="#0a1010" />
            <rect x={28} y={19} width={2} height={2} fill="#0a1010" opacity={0.85} />
          </>
        ) : (
          /* idle — small content smile (less wide than happy) */
          <>
            <rect x={18} y={19} width={2} height={2} fill="#0a1010" />
            <rect x={28} y={19} width={2} height={2} fill="#0a1010" />
            <rect x={19} y={21} width={10} height={1} fill="#0a1010" />
          </>
        )}
        {/* Blush cheeks — below outer corners of eyes */}
        {(mood === "happy" || mood === "excited") && (
          <>
            <rect x={13} y={15} width={3} height={2} fill="#ff8090" opacity={0.45} />
            <rect x={32} y={15} width={3} height={2} fill="#ff8090" opacity={0.45} />
          </>
        )}
      </>
    );
  }

  const cx = 24;
  const eyeY = 17 + (stage >= 3 ? 1 : 0);
  const eyeGap = 7;
  const eyeL = cx - eyeGap - eyes.w;
  const eyeR = cx + eyeGap;

  // Pupil (white dot inside dark eye)
  const pupilW = Math.max(1, eyes.w - 1);
  const pupilH = Math.max(1, eyes.h - 1);

  // Mouth
  const mouthY = eyeY + eyes.h + 4;

  return (
    <>
      {/* Eyes — dark base */}
      <rect x={eyeL} y={eyeY} width={eyes.w} height={eyes.h} fill={colors.eye} />
      <rect x={eyeR} y={eyeY} width={eyes.w} height={eyes.h} fill={colors.eye} />
      {/* Pupils — small white highlight */}
      {eyes.shape !== "sleepy" && (
        <>
          <rect x={eyeL + 1} y={eyeY} width={1} height={1} fill="#fff" opacity={0.8} />
          <rect x={eyeR + 1} y={eyeY} width={1} height={1} fill="#fff" opacity={0.8} />
        </>
      )}
      {/* Star eyes for excited/legendary */}
      {eyes.shape === "star" && (
        <>
          <rect x={eyeL - 1} y={eyeY + 1} width={1} height={1} fill={accent} opacity={0.9} />
          <rect x={eyeR + eyes.w} y={eyeY + 1} width={1} height={1} fill={accent} opacity={0.9} />
        </>
      )}
      {/* Mouth */}
      {mood === "happy" || mood === "excited" ? (
        <>
          <rect x={cx - 3} y={mouthY} width={6} height={2} fill={accent} />
          <rect x={cx - 4} y={mouthY - 1} width={2} height={1} fill={accent} />
          <rect x={cx + 2} y={mouthY - 1} width={2} height={1} fill={accent} />
        </>
      ) : mood === "sleepy" ? (
        <rect x={cx - 2} y={mouthY} width={4} height={1} fill={accent} opacity={0.6} />
      ) : mood === "curious" ? (
        <>
          <rect x={cx - 1} y={mouthY} width={2} height={2} fill={accent} />
          <rect x={cx - 2} y={mouthY + 1} width={4} height={1} fill={accent} />
        </>
      ) : (
        <rect x={cx - 3} y={mouthY} width={6} height={1} fill={accent} opacity={0.7} />
      )}
      {/* Blush marks — visible when happy/excited */}
      {(mood === "happy" || mood === "excited") && (
        <>
          <rect x={eyeL - 3} y={eyeY + eyes.h + 1} width={3} height={1} fill="#ff8080" opacity={0.55} />
          <rect x={eyeR + eyes.w} y={eyeY + eyes.h + 1} width={3} height={1} fill="#ff8080" opacity={0.55} />
        </>
      )}
    </>
  );
}

const SPARKLE_POS = [
  [4, 4], [42, 6], [6, 40], [40, 40], [24, 2], [2, 22],
];

function renderLegendaryCrown(colors: ColorSet, accent: string) {
  return (
    <>
      {/* Crown base bar */}
      <rect x={15} y={5} width={18} height={3} fill={accent} />
      {/* Crown points */}
      <rect x={15} y={2} width={3} height={4} fill={accent} />
      <rect x={22} y={0} width={4} height={6} fill={accent} />
      <rect x={30} y={2} width={3} height={4} fill={accent} />
      {/* Gem in crown */}
      <rect x={23} y={1} width={2} height={2} fill="#fff" opacity={0.9} />
      {/* Halo ring */}
      <rect x={12} y={3} width={24} height={2} rx={1} fill={accent} opacity={0.25} />
    </>
  );
}

function renderSpeciesFeatures(
  species: BuddySpecies,
  stage: EvolutionStage,
  colors: ColorSet,
  accent: string,
) {
  switch (species) {
    case "byte-bat":
      return (
        <>
          {/* Wing left */}
          <rect x={4} y={16} width={8} height={10} rx={2} fill={colors.accent} />
          <rect x={2} y={20} width={4} height={6} rx={1} fill={colors.accent} />
          {/* Wing right */}
          <rect x={36} y={16} width={8} height={10} rx={2} fill={colors.accent} />
          <rect x={42} y={20} width={4} height={6} rx={1} fill={colors.accent} />
          {/* Wing highlight */}
          <rect x={5} y={17} width={3} height={2} fill={colors.highlight} opacity={0.4} />
          <rect x={40} y={17} width={3} height={2} fill={colors.highlight} opacity={0.4} />
          {/* Wing veins stage 1+ */}
          {stage >= 1 && (
            <>
              <rect x={6} y={22} width={1} height={6} fill={colors.shadow} opacity={0.4} />
              <rect x={41} y={22} width={1} height={6} fill={colors.shadow} opacity={0.4} />
            </>
          )}
          {/* Elongated wings stage 2+ */}
          {stage >= 2 && (
            <>
              <rect x={0} y={18} width={5} height={4} rx={1} fill={colors.accent} />
              <rect x={43} y={18} width={5} height={4} rx={1} fill={colors.accent} />
            </>
          )}
          {/* Fangs */}
          <rect x={21} y={28} width={2} height={3} fill={colors.highlight} opacity={0.8} />
          <rect x={25} y={28} width={2} height={3} fill={colors.highlight} opacity={0.8} />
          {/* Ear tufts */}
          <rect x={10} y={8} width={4} height={5} rx={1} fill={colors.accent} />
          <rect x={34} y={8} width={4} height={5} rx={1} fill={colors.accent} />
        </>
      );

    case "data-fox":
      return (
        <>
          {/* Pointy ears */}
          <rect x={10} y={4} width={5} height={8} rx={2} fill={colors.accent} />
          <rect x={11} y={5} width={3} height={5} fill={colors.body} opacity={0.5} />
          <rect x={33} y={4} width={5} height={8} rx={2} fill={colors.accent} />
          <rect x={34} y={5} width={3} height={5} fill={colors.body} opacity={0.5} />
          {/* Muzzle */}
          <rect x={18} y={24} width={12} height={6} rx={3} fill={colors.accent} opacity={0.6} />
          <rect x={22} y={26} width={4} height={2} fill={colors.eye} opacity={0.5} />
          {/* Tail */}
          <rect x={34} y={32} width={6} height={8} rx={3} fill={colors.accent} />
          <rect x={36} y={34} width={4} height={4} fill={colors.highlight} opacity={0.4} />
          {stage >= 1 && <rect x={38} y={30} width={4} height={6} rx={2} fill={colors.accent} />}
          {stage >= 2 && (
            <>
              {/* Fluffy tail tip — white */}
              <rect x={38} y={36} width={4} height={4} rx={2} fill="#fff5e0" opacity={0.8} />
            </>
          )}
          {/* Paws */}
          <rect x={14} y={42} width={5} height={3} rx={2} fill={colors.body} />
          <rect x={29} y={42} width={5} height={3} rx={2} fill={colors.body} />
        </>
      );

    case "circuit-cat":
      return (
        <>
          {/* Pointy ears */}
          <rect x={10} y={4} width={5} height={7} rx={1} fill={colors.body} />
          <rect x={12} y={5} width={2} height={4} fill={colors.accent} opacity={0.6} />
          <rect x={33} y={4} width={5} height={7} rx={1} fill={colors.body} />
          <rect x={34} y={5} width={2} height={4} fill={colors.accent} opacity={0.6} />
          {/* Whiskers left */}
          <rect x={2} y={23} width={10} height={1} fill={colors.accent} opacity={0.6} />
          <rect x={2} y={25} width={10} height={1} fill={colors.accent} opacity={0.6} />
          <rect x={3} y={21} width={8} height={1} fill={colors.accent} opacity={0.4} />
          {/* Whiskers right */}
          <rect x={36} y={23} width={10} height={1} fill={colors.accent} opacity={0.6} />
          <rect x={36} y={25} width={10} height={1} fill={colors.accent} opacity={0.6} />
          <rect x={37} y={21} width={8} height={1} fill={colors.accent} opacity={0.4} />
          {/* Circuit board markings stage 1+ */}
          {stage >= 1 && (
            <>
              <rect x={16} y={30} width={2} height={8} fill={colors.accent} opacity={0.4} />
              <rect x={16} y={35} width={6} height={2} fill={colors.accent} opacity={0.4} />
              <rect x={30} y={30} width={2} height={8} fill={colors.accent} opacity={0.4} />
              <rect x={26} y={35} width={6} height={2} fill={colors.accent} opacity={0.4} />
            </>
          )}
          {/* Glowing circuit dots stage 2+ */}
          {stage >= 2 && (
            <>
              <rect x={20} y={34} width={3} height={3} rx={1} fill={colors.accent}>
                <animate attributeName="opacity" values="1;0.3;1" dur="1.8s" repeatCount="indefinite" />
              </rect>
              <rect x={25} y={34} width={3} height={3} rx={1} fill={colors.accent}>
                <animate attributeName="opacity" values="0.3;1;0.3" dur="1.8s" repeatCount="indefinite" />
              </rect>
            </>
          )}
          {/* Tail */}
          <rect x={36} y={36} width={8} height={5} rx={3} fill={colors.body} />
          <rect x={40} y={32} width={5} height={6} rx={3} fill={colors.body} />
        </>
      );

    case "logic-lizard":
      return (
        <>
          {/* Dorsal spines */}
          <rect x={22} y={6} width={4} height={6} rx={1} fill={colors.accent} />
          {stage >= 1 && (
            <>
              <rect x={18} y={7} width={3} height={5} rx={1} fill={colors.accent} opacity={0.8} />
              <rect x={27} y={7} width={3} height={5} rx={1} fill={colors.accent} opacity={0.8} />
            </>
          )}
          {stage >= 2 && (
            <>
              <rect x={14} y={9} width={3} height={4} rx={1} fill={colors.accent} opacity={0.6} />
              <rect x={31} y={9} width={3} height={4} rx={1} fill={colors.accent} opacity={0.6} />
            </>
          )}
          {/* Tail — long + segmented */}
          <rect x={34} y={34} width={8} height={5} rx={2} fill={colors.accent} />
          <rect x={38} y={30} width={6} height={6} rx={2} fill={colors.accent} />
          {stage >= 1 && <rect x={42} y={26} width={4} height={5} rx={2} fill={colors.accent} opacity={0.8} />}
          {/* Tongue */}
          <rect x={22} y={30} width={4} height={2} fill="#ff4444" />
          <rect x={21} y={32} width={2} height={2} fill="#ff4444" />
          <rect x={25} y={32} width={2} height={2} fill="#ff4444" />
          {/* Scale pattern on body */}
          <rect x={17} y={30} width={3} height={3} rx={1} fill={colors.highlight} opacity={0.3} />
          <rect x={22} y={32} width={3} height={3} rx={1} fill={colors.highlight} opacity={0.3} />
          <rect x={28} y={30} width={3} height={3} rx={1} fill={colors.highlight} opacity={0.3} />
        </>
      );

    case "hash-hamster":
      return (
        <>
          {/* Big chubby cheeks */}
          <rect x={6} y={16} width={9} height={9} rx={4} fill={colors.accent} opacity={0.6} />
          <rect x={33} y={16} width={9} height={9} rx={4} fill={colors.accent} opacity={0.6} />
          {/* Cheek highlight */}
          <rect x={7} y={17} width={3} height={2} fill={colors.highlight} opacity={0.4} />
          <rect x={38} y={17} width={3} height={2} fill={colors.highlight} opacity={0.4} />
          {/* Round belly */}
          <rect x={14} y={34} width={20} height={10} rx={5} fill={colors.highlight} opacity={0.35} />
          {/* Tiny paws */}
          <rect x={12} y={40} width={6} height={4} rx={3} fill={colors.body} />
          <rect x={30} y={40} width={6} height={4} rx={3} fill={colors.body} />
          {/* Round ears */}
          <rect x={10} y={6} width={7} height={7} rx={3} fill={colors.body} />
          <rect x={31} y={6} width={7} height={7} rx={3} fill={colors.body} />
          <rect x={12} y={7} width={4} height={4} rx={2} fill={colors.accent} opacity={0.5} />
          <rect x={32} y={7} width={4} height={4} rx={2} fill={colors.accent} opacity={0.5} />
          {/* Seed in hand stage 1+ */}
          {stage >= 1 && (
            <rect x={20} y={42} width={8} height={4} rx={2} fill={colors.accent} opacity={0.7} />
          )}
          {/* Hash mark pattern on belly stage 2+ */}
          {stage >= 2 && (
            <>
              <rect x={19} y={36} width={10} height={1} fill={colors.shadow} opacity={0.3} />
              <rect x={21} y={38} width={6} height={1} fill={colors.shadow} opacity={0.3} />
              <rect x={22} y={34} width={1} height={5} fill={colors.shadow} opacity={0.3} />
              <rect x={25} y={34} width={1} height={5} fill={colors.shadow} opacity={0.3} />
            </>
          )}
        </>
      );

    case "bmo": {
      // Body: x=9–38, y=3–41. Screen: x=12–35, y=8–25. Feet below y=42.
      return (
        <>
          {/* ── Arms ── chunky, centered on y=24–30 (below screen, above buttons) */}
          {/* Left arm */}
          <rect x={2} y={24} width={7} height={7} rx={3} fill={colors.body} />
          <rect x={1} y={27} width={4} height={4} rx={2} fill={colors.body} />
          <rect x={3} y={25} width={3} height={2} fill={colors.highlight} opacity={0.45} />
          {/* Right arm */}
          <rect x={39} y={24} width={7} height={7} rx={3} fill={colors.body} />
          <rect x={43} y={27} width={4} height={4} rx={2} fill={colors.body} />
          <rect x={40} y={25} width={3} height={2} fill={colors.highlight} opacity={0.45} />

          {/* ── Feet ── wide stumps below the console */}
          <rect x={11} y={42} width={9} height={5} rx={2} fill={colors.body} />
          <rect x={28} y={42} width={9} height={5} rx={2} fill={colors.body} />

          {/* ── D-pad ── proper plus/cross shape */}
          {/* Horizontal bar */}
          <rect x={12} y={33} width={10} height={3} rx={1} fill={colors.shadow} opacity={0.78} />
          {/* Vertical bar */}
          <rect x={16} y={29} width={3} height={9} rx={1} fill={colors.shadow} opacity={0.78} />
          {/* Center highlight cap */}
          <rect x={16} y={33} width={3} height={3} fill={colors.body} opacity={0.55} />

          {/* ── A button (red) — upper right ── */}
          <rect x={28} y={28} width={6} height={6} rx={3} fill="#e05555" />
          <rect x={29} y={29} width={2} height={2} fill="#ff9090" opacity={0.65} />
          {/* ── B button (accent) — lower right, offset diagonally ── */}
          <rect x={32} y={33} width={6} height={6} rx={3} fill={colors.accent} />
          <rect x={33} y={34} width={2} height={2} fill="#fffacc" opacity={0.55} />

          {/* ── Select / Start ── small centre buttons */}
          <rect x={21} y={38} width={4} height={2} rx={1} fill={colors.shadow} opacity={0.65} />
          <rect x={26} y={38} width={4} height={2} rx={1} fill={colors.shadow} opacity={0.65} />

          {/* ── Stage 1+: Cartridge slot on bottom edge ── */}
          {stage >= 1 && (
            <>
              <rect x={17} y={40} width={14} height={2} rx={1} fill={colors.shadow} opacity={0.55} />
              <rect x={18} y={40} width={12} height={1} fill={colors.highlight} opacity={0.2} />
            </>
          )}

          {/* ── Stage 2+: CRT scanlines on screen + blue button ── */}
          {stage >= 2 && (
            <>
              <rect x={13} y={12} width={22} height={1} fill="#ffffff" opacity={0.06} />
              <rect x={13} y={16} width={22} height={1} fill="#ffffff" opacity={0.06} />
              <rect x={13} y={20} width={22} height={1} fill="#ffffff" opacity={0.06} />
              {/* Blue button between D-pad and A */}
              <rect x={24} y={28} width={4} height={4} rx={2} fill="#6ab4ff" />
              <rect x={25} y={29} width={1} height={1} fill="#c8eeff" opacity={0.7} />
            </>
          )}

          {/* ── Stage 3 only: Carry handle + blinking LED (stage 4 gets crown) ── */}
          {stage === 3 && (
            <>
              {/* Handle arch above console top */}
              <rect x={14} y={0} width={20} height={5} rx={2} fill={colors.shadow} opacity={0.82} />
              <rect x={15} y={1} width={18} height={3} rx={1} fill={colors.body} opacity={0.9} />
              {/* Blinking status LED */}
              <rect x={10} y={37} width={3} height={3} rx={1} fill="#66ff88">
                <animate attributeName="opacity" values="1;0.2;1" dur="2.2s" repeatCount="indefinite" />
              </rect>
            </>
          )}

          {/* ── Stage 4: Gold screen border + rainbow speaker dots + LED ── */}
          {stage >= 4 && (
            <>
              {/* Golden trim around screen bezel */}
              <rect x={10} y={6} width={28} height={22} rx={2} fill="none" stroke={colors.accent} strokeWidth={2} strokeOpacity={0.92} />
              {/* Rainbow speaker dots */}
              <rect x={10} y={40} width={2} height={2} rx={1} fill="#6abaff" opacity={0.9} />
              <rect x={13} y={40} width={2} height={2} rx={1} fill="#ff88cc" opacity={0.9} />
              <rect x={16} y={40} width={2} height={2} rx={1} fill="#88ff88" opacity={0.9} />
              {/* LED always lit */}
              <rect x={10} y={37} width={3} height={3} rx={1} fill="#66ff88" opacity={0.92} />
            </>
          )}
        </>
      );
    }

    default: // pixel-sprite
      return (
        <>
          {/* Antenna */}
          <rect x={23} y={4} width={2} height={7} fill={colors.accent} />
          <rect x={21} y={3} width={6} height={3} rx={1} fill={colors.accent} />
          <rect x={22} y={2} width={4} height={2} rx={1} fill={colors.highlight} opacity={0.6} />
          {/* Side panels */}
          <rect x={6} y={20} width={4} height={10} rx={2} fill={colors.accent} opacity={0.5} />
          <rect x={38} y={20} width={4} height={10} rx={2} fill={colors.accent} opacity={0.5} />
          {/* Chest panel */}
          <rect x={16} y={32} width={16} height={8} rx={2} fill={colors.accent} opacity={0.3} />
          <rect x={19} y={34} width={4} height={4} rx={1} fill={colors.accent} opacity={0.6} />
          <rect x={25} y={34} width={4} height={4} rx={1} fill={colors.accent} opacity={0.6} />
          {/* Blinking light stage 1+ */}
          {stage >= 1 && (
            <rect x={23} y={35} width={2} height={2} rx={1} fill={colors.highlight}>
              <animate attributeName="opacity" values="1;0.2;1" dur="2s" repeatCount="indefinite" />
            </rect>
          )}
          {/* Extra arm panels stage 2+ */}
          {stage >= 2 && (
            <>
              <rect x={4} y={26} width={4} height={3} rx={1} fill={colors.highlight} opacity={0.5} />
              <rect x={40} y={26} width={4} height={3} rx={1} fill={colors.highlight} opacity={0.5} />
            </>
          )}
        </>
      );
  }
}

/* ─────────────────────────────────── data ── */

interface ColorSet {
  body: string;
  highlight: string;
  shadow: string;
  accent: string;
  eye: string;
}

/** 5 stages: 0=egg/baby, 1=child, 2=teen, 3=adult, 4=legendary */
const SPECIES_PALETTES: Record<string, Record<number, ColorSet>> = {
  "pixel-sprite": {
    0: { body: "#7dd3fc", highlight: "#bae6fd", shadow: "#3b82f6", accent: "#fde047", eye: "#1e293b" },
    1: { body: "#60a5fa", highlight: "#93c5fd", shadow: "#2563eb", accent: "#fbbf24", eye: "#1e293b" },
    2: { body: "#3b82f6", highlight: "#93c5fd", shadow: "#1d4ed8", accent: "#f59e0b", eye: "#0f172a" },
    3: { body: "#2563eb", highlight: "#60a5fa", shadow: "#1e3a8a", accent: "#f97316", eye: "#0f172a" },
    4: { body: "#1d4ed8", highlight: "#3b82f6", shadow: "#172554", accent: "#ff6b35", eye: "#fff" },
  },
  "byte-bat": {
    0: { body: "#a78bfa", highlight: "#c4b5fd", shadow: "#6d28d9", accent: "#ddd6fe", eye: "#fecaca" },
    1: { body: "#8b5cf6", highlight: "#a78bfa", shadow: "#5b21b6", accent: "#c4b5fd", eye: "#fca5a5" },
    2: { body: "#7c3aed", highlight: "#8b5cf6", shadow: "#4c1d95", accent: "#a78bfa", eye: "#f87171" },
    3: { body: "#6d28d9", highlight: "#7c3aed", shadow: "#3b0764", accent: "#8b5cf6", eye: "#ef4444" },
    4: { body: "#4c1d95", highlight: "#6d28d9", shadow: "#1e0a3c", accent: "#e879f9", eye: "#fde047" },
  },
  "data-fox": {
    0: { body: "#fdba74", highlight: "#fed7aa", shadow: "#ea580c", accent: "#fde68a", eye: "#1e293b" },
    1: { body: "#fb923c", highlight: "#fdba74", shadow: "#c2410c", accent: "#fbbf24", eye: "#1e293b" },
    2: { body: "#f97316", highlight: "#fb923c", shadow: "#9a3412", accent: "#f59e0b", eye: "#0f172a" },
    3: { body: "#ea580c", highlight: "#f97316", shadow: "#7c2d12", accent: "#fbbf24", eye: "#0f172a" },
    4: { body: "#c2410c", highlight: "#ea580c", shadow: "#431407", accent: "#fde047", eye: "#fefce8" },
  },
  "circuit-cat": {
    0: { body: "#94a3b8", highlight: "#cbd5e1", shadow: "#475569", accent: "#67e8f9", eye: "#22d3ee" },
    1: { body: "#64748b", highlight: "#94a3b8", shadow: "#334155", accent: "#22d3ee", eye: "#06b6d4" },
    2: { body: "#475569", highlight: "#64748b", shadow: "#1e293b", accent: "#0891b2", eye: "#06b6d4" },
    3: { body: "#334155", highlight: "#475569", shadow: "#0f172a", accent: "#0e7490", eye: "#22d3ee" },
    4: { body: "#1e293b", highlight: "#334155", shadow: "#020617", accent: "#00ffff", eye: "#f0f9ff" },
  },
  "logic-lizard": {
    0: { body: "#86efac", highlight: "#bbf7d0", shadow: "#16a34a", accent: "#4ade80", eye: "#1e293b" },
    1: { body: "#4ade80", highlight: "#86efac", shadow: "#15803d", accent: "#22c55e", eye: "#1e293b" },
    2: { body: "#22c55e", highlight: "#4ade80", shadow: "#166534", accent: "#16a34a", eye: "#0f172a" },
    3: { body: "#16a34a", highlight: "#22c55e", shadow: "#14532d", accent: "#15803d", eye: "#0f172a" },
    4: { body: "#15803d", highlight: "#16a34a", shadow: "#052e16", accent: "#84cc16", eye: "#f0fdf4" },
  },
  "hash-hamster": {
    0: { body: "#fde68a", highlight: "#fef3c7", shadow: "#d97706", accent: "#fbbf24", eye: "#1e293b" },
    1: { body: "#fbbf24", highlight: "#fde68a", shadow: "#b45309", accent: "#f59e0b", eye: "#1e293b" },
    2: { body: "#f59e0b", highlight: "#fbbf24", shadow: "#92400e", accent: "#d97706", eye: "#0f172a" },
    3: { body: "#d97706", highlight: "#f59e0b", shadow: "#78350f", accent: "#b45309", eye: "#0f172a" },
    4: { body: "#b45309", highlight: "#d97706", shadow: "#451a03", accent: "#fde047", eye: "#fefce8" },
  },
  // BMO — Adventure Time's game-console companion (cyan-teal, 5 stages)
  "bmo": {
    0: { body: "#5dcec2", highlight: "#8de2db", shadow: "#1d8878", accent: "#ffd166", eye: "#071510" },
    1: { body: "#4bbdb2", highlight: "#7ad4cc", shadow: "#167868", accent: "#f4a261", eye: "#071510" },
    2: { body: "#3aada2", highlight: "#68c6be", shadow: "#106858", accent: "#e9c46a", eye: "#071510" },
    3: { body: "#2a9d92", highlight: "#58b8b0", shadow: "#0a5848", accent: "#f4c842", eye: "#071510" },
    4: { body: "#1a8d82", highlight: "#48a8a0", shadow: "#044838", accent: "#ffd700", eye: "#c8ffee" },
  },
};

interface EyeDef { w: number; h: number; shape: "normal" | "happy" | "sleepy" | "star" }

/** Eye shapes per mood — in 48×48 pixel units */
const MOOD_EYES: Record<string, EyeDef> = {
  happy:   { w: 5, h: 3, shape: "happy" },
  curious: { w: 5, h: 6, shape: "normal" },
  sleepy:  { w: 5, h: 2, shape: "sleepy" },
  excited: { w: 6, h: 6, shape: "star" },
  idle:    { w: 5, h: 5, shape: "normal" },
};

/** Mood-based accent color overrides */
const MOOD_ACCENT: Record<string, string | null> = {
  happy:   null,
  curious: "#a78bfa",
  sleepy:  "#94a3b8",
  excited: "#fbbf24",
  idle:    null,
};
