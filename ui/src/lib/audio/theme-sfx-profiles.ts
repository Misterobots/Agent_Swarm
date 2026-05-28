/**
 * Per-theme UI sound profiles.
 *
 * Each profile describes the synthesized parameters for the 4 global UI sounds
 * (hover, click, keystroke, error). Profiles are pure data — `ui-sfx.ts`
 * consumes them via the Web Audio API.
 *
 * A null entry means "silent for this action under this theme". Some themes
 * (memex-archive, bladerunner) intentionally silence keystrokes for
 * library/noir atmosphere.
 *
 * Design philosophy:
 * - Standard / professional themes (memex, minimal, slate, signal, office,
 *   memex-archive): refined, soft, almost imperceptible. Should not distract.
 * - Playful / thematic themes: distinct timbre that matches the visual
 *   personality. LCARS gets the square-wave button beep, hacker/terminal get
 *   mechanical clicks, cyberpunk gets glitchy detuned tones, etc.
 *
 * Volume note: keystroke `gain` is capped low across the board — keystrokes
 * fire on every keypress and quickly become annoying if loud.
 */

import type { ChatTheme } from "@/lib/stores/settings-store";

/** Single oscillator with optional pitch glide and gain envelope. */
export interface ToneSpec {
  type: OscillatorType;
  /** Hz at start */
  freqStart: number;
  /** Hz at end of duration */
  freqEnd: number;
  /** seconds */
  duration: number;
  /** 0..1 peak gain */
  gain: number;
  /** seconds to ramp from 0 → gain (default 0.005) */
  attack?: number;
  /** decay curve from peak to silence (default 'exponential') */
  curve?: "linear" | "exponential";
  /** Optional harmonic layered on top (richer textures) */
  harmonic?: { type: OscillatorType; freq: number; gain: number };
  /** Optional white-noise burst layered on top (for mechanical/percussive sounds) */
  noise?: { duration: number; gain: number; highpass?: number; lowpass?: number };
  /** Optional delay before the tone (ms) — for staggered 2-tone clicks */
  delayMs?: number;
  /** Optional second tone fired after delayMs2 — for 2-tone LCARS-style beeps */
  followup?: ToneSpec & { delayMs2: number };
}

export interface SoundProfile {
  hover: ToneSpec | null;
  click: ToneSpec | null;
  keystroke: ToneSpec | null;
  error: ToneSpec | null;
}

// ---------------------------------------------------------------------------
// Profile presets — referenced by theme map below
// ---------------------------------------------------------------------------

/**
 * Professional / refined — used for memex, minimal, slate, signal, office,
 * memex-archive. Soft sine tones, very low gain. Almost subliminal.
 */
const PROFILE_PROFESSIONAL: SoundProfile = {
  hover:     { type: "sine",     freqStart: 1400, freqEnd: 1100, duration: 0.04, gain: 0.03 },
  click:     { type: "sine",     freqStart:  900, freqEnd:  500, duration: 0.08, gain: 0.06 },
  keystroke: { type: "triangle", freqStart:  600, freqEnd:  150, duration: 0.02, gain: 0.02 },
  error:     { type: "sine",     freqStart:  300, freqEnd:  200, duration: 0.22, gain: 0.06 },
};

/** Memex-archive — like professional but keystroke is silent (library hush). */
const PROFILE_ARCHIVE: SoundProfile = {
  ...PROFILE_PROFESSIONAL,
  keystroke: null,
  hover:     { type: "sine", freqStart: 1100, freqEnd: 950, duration: 0.05, gain: 0.025 },
};

/** Minimal — even softer than professional. Quiet by design. */
const PROFILE_MINIMAL: SoundProfile = {
  hover:     { type: "sine",     freqStart: 1600, freqEnd: 1500, duration: 0.025, gain: 0.018 },
  click:     { type: "sine",     freqStart: 1000, freqEnd:  700, duration: 0.05,  gain: 0.04 },
  keystroke: { type: "triangle", freqStart:  500, freqEnd:  200, duration: 0.018, gain: 0.012 },
  error:     { type: "sine",     freqStart:  400, freqEnd:  300, duration: 0.15,  gain: 0.045 },
};

/**
 * LCARS / Starfleet — the iconic square-wave button beep. Distinct, instantly
 * recognizable. Two-tone for clicks ("boop-beep"). Used for lcars, lcars-blue,
 * lcars-teal, star-trek.
 */
const PROFILE_LCARS: SoundProfile = {
  hover:     { type: "square", freqStart: 1200, freqEnd: 1200, duration: 0.04, gain: 0.05 },
  click:     {
    type: "square", freqStart: 880, freqEnd: 880, duration: 0.06, gain: 0.08,
    followup: { type: "square", freqStart: 1320, freqEnd: 1320, duration: 0.07, gain: 0.07, delayMs2: 70 },
  },
  keystroke: { type: "square", freqStart: 1500, freqEnd: 1500, duration: 0.02, gain: 0.025 },
  error:     { type: "square", freqStart:  200, freqEnd:  150, duration: 0.30, gain: 0.10 },
};

/**
 * Hacker / Terminal — sharp mechanical key clicks. Noise-driven for that
 * "mechanical switch" feel. Keystroke is the star here.
 */
const PROFILE_TERMINAL: SoundProfile = {
  hover: { type: "triangle", freqStart: 1500, freqEnd: 1400, duration: 0.02, gain: 0.025 },
  click: {
    type: "square", freqStart: 600, freqEnd: 200, duration: 0.04, gain: 0.07,
    noise: { duration: 0.025, gain: 0.08, highpass: 2000 },
  },
  keystroke: {
    type: "triangle", freqStart: 350, freqEnd: 80, duration: 0.025, gain: 0.04,
    noise: { duration: 0.015, gain: 0.05, highpass: 3000 },
  },
  error: { type: "sawtooth", freqStart: 180, freqEnd: 90, duration: 0.25, gain: 0.10 },
};

/** Hacker — same family as terminal but slightly more aggressive on the noise burst. */
const PROFILE_HACKER: SoundProfile = {
  ...PROFILE_TERMINAL,
  keystroke: {
    type: "square", freqStart: 280, freqEnd: 80, duration: 0.03, gain: 0.045,
    noise: { duration: 0.02, gain: 0.07, highpass: 2500 },
  },
};

/**
 * Cyberpunk / Shadowrun — glitchy, detuned, slightly distorted. Sawtooth +
 * dissonant harmonic creates that "hacked-in" feel.
 */
const PROFILE_CYBERPUNK: SoundProfile = {
  hover: {
    type: "sawtooth", freqStart: 1100, freqEnd: 950, duration: 0.04, gain: 0.04,
    harmonic: { type: "square", freq: 2210, gain: 0.015 },
  },
  click: {
    type: "sawtooth", freqStart: 700, freqEnd: 320, duration: 0.09, gain: 0.08,
    harmonic: { type: "square", freq: 1410, gain: 0.03 },
  },
  keystroke: { type: "sawtooth", freqStart: 500, freqEnd: 150, duration: 0.025, gain: 0.025 },
  error: {
    type: "sawtooth", freqStart: 220, freqEnd: 110, duration: 0.32, gain: 0.10,
    harmonic: { type: "square", freq: 145, gain: 0.04 },
  },
};

/**
 * Forge (amber / ember) — warm, dampened, metallic. Like striking an anvil
 * lightly. Lower frequencies, longer decay tails.
 */
const PROFILE_FORGE: SoundProfile = {
  hover: { type: "triangle", freqStart: 700, freqEnd: 500, duration: 0.06, gain: 0.035 },
  click: {
    type: "sine", freqStart: 400, freqEnd: 180, duration: 0.18, gain: 0.07,
    harmonic: { type: "triangle", freq: 800, gain: 0.025 },
  },
  keystroke: { type: "triangle", freqStart: 350, freqEnd: 130, duration: 0.025, gain: 0.018 },
  error: { type: "sine", freqStart: 180, freqEnd: 100, duration: 0.30, gain: 0.09 },
};

/**
 * HAL 9000 — smooth, ominous, perfectly calm. Pure sine, low pitch, slow
 * decay. Keystrokes are silent — HAL doesn't acknowledge typing.
 */
const PROFILE_HAL: SoundProfile = {
  hover: { type: "sine", freqStart: 320, freqEnd: 320, duration: 0.06, gain: 0.045 },
  click: { type: "sine", freqStart: 220, freqEnd: 180, duration: 0.20, gain: 0.07 },
  keystroke: null,
  error: { type: "sine", freqStart: 140, freqEnd: 100, duration: 0.45, gain: 0.08 },
};

/**
 * Nostromo / MU-TH-UR — industrial, mechanical. Beeps that sound like 70s
 * ship computer. Lower fidelity, square-wave-forward.
 */
const PROFILE_NOSTROMO: SoundProfile = {
  hover: { type: "square", freqStart: 600, freqEnd: 600, duration: 0.05, gain: 0.04 },
  click: {
    type: "square", freqStart: 420, freqEnd: 420, duration: 0.10, gain: 0.07,
    noise: { duration: 0.05, gain: 0.025, lowpass: 800 },
  },
  keystroke: { type: "square", freqStart: 280, freqEnd: 200, duration: 0.025, gain: 0.022 },
  error: {
    type: "square", freqStart: 160, freqEnd: 110, duration: 0.40, gain: 0.10,
    noise: { duration: 0.30, gain: 0.04, lowpass: 1200 },
  },
};

/**
 * Tron — bright synth-Grid feel. Triangle base + sine harmonic for that
 * Wendy Carlos synthesizer character.
 */
const PROFILE_TRON: SoundProfile = {
  hover: {
    type: "triangle", freqStart: 1500, freqEnd: 1300, duration: 0.04, gain: 0.04,
    harmonic: { type: "sine", freq: 3000, gain: 0.02 },
  },
  click: {
    type: "triangle", freqStart: 800, freqEnd: 400, duration: 0.10, gain: 0.08,
    harmonic: { type: "sine", freq: 1600, gain: 0.04 },
  },
  keystroke: { type: "triangle", freqStart: 600, freqEnd: 250, duration: 0.025, gain: 0.025 },
  error: { type: "sawtooth", freqStart: 240, freqEnd: 140, duration: 0.28, gain: 0.10 },
};

/**
 * Bladerunner — noir, atmospheric, sparse. Hovers are silent. Clicks are
 * deep and short. Keystrokes silent. Maximum mood.
 */
const PROFILE_BLADERUNNER: SoundProfile = {
  hover: null,
  click: { type: "sine", freqStart: 260, freqEnd: 180, duration: 0.18, gain: 0.05 },
  keystroke: null,
  error: { type: "sine", freqStart: 130, freqEnd: 90, duration: 0.50, gain: 0.07 },
};

/**
 * Dune — mystical, ceremonial. Soft bell-like tones with longer decay.
 * Evokes Bene Gesserit / Mentat focus.
 */
const PROFILE_DUNE: SoundProfile = {
  hover: {
    type: "sine", freqStart: 1320, freqEnd: 1320, duration: 0.08, gain: 0.03,
    harmonic: { type: "sine", freq: 2640, gain: 0.012 },
  },
  click: {
    type: "sine", freqStart: 660, freqEnd: 660, duration: 0.25, gain: 0.06,
    harmonic: { type: "sine", freq: 1320, gain: 0.025 },
  },
  keystroke: { type: "sine", freqStart: 800, freqEnd: 600, duration: 0.025, gain: 0.015 },
  error: { type: "sine", freqStart: 200, freqEnd: 150, duration: 0.40, gain: 0.07 },
};

/**
 * Ops / Mission Control — tactical comm beep. Clean and short, no nonsense.
 * Think "radio click" before a transmission.
 */
const PROFILE_OPS: SoundProfile = {
  hover: { type: "square", freqStart: 1800, freqEnd: 1800, duration: 0.025, gain: 0.03 },
  click: { type: "square", freqStart: 1000, freqEnd: 1000, duration: 0.05, gain: 0.07 },
  keystroke: { type: "triangle", freqStart: 500, freqEnd: 200, duration: 0.018, gain: 0.018 },
  error: { type: "square", freqStart: 280, freqEnd: 200, duration: 0.25, gain: 0.09 },
};

// ---------------------------------------------------------------------------
// Theme → profile map
// ---------------------------------------------------------------------------

export const THEME_SFX_PROFILES: Record<ChatTheme, SoundProfile> = {
  // Standard / professional
  memex:           PROFILE_PROFESSIONAL,
  minimal:         PROFILE_MINIMAL,
  slate:           PROFILE_PROFESSIONAL,
  signal:          PROFILE_OPS,             // signal = comm intel, ops profile fits
  office:          PROFILE_PROFESSIONAL,
  "memex-archive": PROFILE_ARCHIVE,

  // LCARS / Starfleet
  lcars:           PROFILE_LCARS,
  "lcars-blue":    PROFILE_LCARS,
  "lcars-teal":    PROFILE_LCARS,
  "star-trek":     PROFILE_LCARS,

  // Forge
  amber:           PROFILE_FORGE,
  ember:           PROFILE_FORGE,

  // Terminal / Hacker
  terminal:        PROFILE_TERMINAL,
  hacker:          PROFILE_HACKER,

  // Cyberpunk / Shadowrun
  cyberpunk:       PROFILE_CYBERPUNK,
  shadowrun:       PROFILE_CYBERPUNK,

  // Themed personalities
  hal9000:         PROFILE_HAL,
  nostromo:        PROFILE_NOSTROMO,
  tron:            PROFILE_TRON,
  bladerunner:     PROFILE_BLADERUNNER,
  dune:            PROFILE_DUNE,

  // Tactical
  ops:             PROFILE_OPS,
};
