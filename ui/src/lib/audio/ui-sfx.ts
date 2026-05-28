"use client";

/**
 * Theme-aware UI sound effects.
 *
 * All sounds are synthesized via the Web Audio API from per-theme profiles
 * defined in `theme-sfx-profiles.ts`. Profile lookup is keyed on the active
 * `theme` from the settings store; the caller passes it explicitly so we can
 * keep this module side-effect free and tree-shake friendly.
 *
 * Pass `theme = null` (or omit) to use the legacy default profile — useful
 * during transitions or for tests.
 */

import type { ChatTheme } from "@/lib/stores/settings-store";
import {
  THEME_SFX_PROFILES,
  type SoundProfile,
  type ToneSpec,
} from "./theme-sfx-profiles";

// Single shared AudioContext — created lazily on first interaction
let audioCtx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

// Legacy default — used when no theme is provided (matches the previous
// pre-theme defaults so behavior is identical for code paths not yet updated).
const DEFAULT_PROFILE: SoundProfile = {
  hover:     { type: "sine",     freqStart: 1200, freqEnd:  800, duration: 0.05, gain: 0.05 },
  click:     { type: "square",   freqStart:  800, freqEnd:  300, duration: 0.10, gain: 0.10 },
  keystroke: { type: "triangle", freqStart:  500, freqEnd:  100, duration: 0.03, gain: 0.03 },
  error:     { type: "sawtooth", freqStart:  150, freqEnd:  100, duration: 0.20, gain: 0.10, curve: "linear" },
};

function getProfile(theme: ChatTheme | null | undefined): SoundProfile {
  if (!theme) return DEFAULT_PROFILE;
  return THEME_SFX_PROFILES[theme] ?? DEFAULT_PROFILE;
}

// ---------------------------------------------------------------------------
// Core renderer — synthesize one ToneSpec at a given start time
// ---------------------------------------------------------------------------

function renderTone(ctx: AudioContext, spec: ToneSpec, when: number): void {
  const attack = spec.attack ?? 0.005;
  const curve = spec.curve ?? "exponential";

  // Primary oscillator
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = spec.type;
  osc.frequency.setValueAtTime(spec.freqStart, when);
  if (spec.freqEnd !== spec.freqStart) {
    if (curve === "linear") {
      osc.frequency.linearRampToValueAtTime(spec.freqEnd, when + spec.duration);
    } else {
      // exponentialRampToValueAtTime cannot accept 0 — clamp to small positive
      osc.frequency.exponentialRampToValueAtTime(Math.max(spec.freqEnd, 1), when + spec.duration);
    }
  }
  gain.gain.setValueAtTime(0, when);
  gain.gain.linearRampToValueAtTime(spec.gain, when + attack);
  if (curve === "linear") {
    gain.gain.linearRampToValueAtTime(0, when + spec.duration);
  } else {
    gain.gain.exponentialRampToValueAtTime(0.001, when + spec.duration);
  }
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(when);
  osc.stop(when + spec.duration + 0.01);

  // Optional harmonic layer
  if (spec.harmonic) {
    const hOsc = ctx.createOscillator();
    const hGain = ctx.createGain();
    hOsc.type = spec.harmonic.type;
    hOsc.frequency.setValueAtTime(spec.harmonic.freq, when);
    hGain.gain.setValueAtTime(0, when);
    hGain.gain.linearRampToValueAtTime(spec.harmonic.gain, when + attack);
    hGain.gain.exponentialRampToValueAtTime(0.001, when + spec.duration);
    hOsc.connect(hGain);
    hGain.connect(ctx.destination);
    hOsc.start(when);
    hOsc.stop(when + spec.duration + 0.01);
  }

  // Optional noise burst (for mechanical/percussive textures)
  if (spec.noise) {
    const noiseBuf = makeNoiseBuffer(ctx, spec.noise.duration);
    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuf;

    let dest: AudioNode = ctx.destination;

    // Optional lowpass
    if (spec.noise.lowpass) {
      const lp = ctx.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = spec.noise.lowpass;
      lp.connect(dest);
      dest = lp;
    }
    // Optional highpass
    if (spec.noise.highpass) {
      const hp = ctx.createBiquadFilter();
      hp.type = "highpass";
      hp.frequency.value = spec.noise.highpass;
      hp.connect(dest);
      dest = hp;
    }

    const nGain = ctx.createGain();
    nGain.gain.setValueAtTime(spec.noise.gain, when);
    nGain.gain.exponentialRampToValueAtTime(0.001, when + spec.noise.duration);
    noise.connect(nGain);
    nGain.connect(dest);
    noise.start(when);
    noise.stop(when + spec.noise.duration + 0.01);
  }

  // Optional follow-up tone (2-tone beeps, e.g. LCARS)
  if (spec.followup) {
    renderTone(ctx, spec.followup, when + spec.followup.delayMs2 / 1000);
  }
}

function makeNoiseBuffer(ctx: AudioContext, duration: number): AudioBuffer {
  const sampleRate = ctx.sampleRate;
  const length = Math.max(1, Math.floor(sampleRate * duration));
  const buf = ctx.createBuffer(1, length, sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < length; i++) {
    data[i] = Math.random() * 2 - 1;
  }
  return buf;
}

function play(spec: ToneSpec | null): void {
  if (!spec) return; // silent for this action under this theme
  const ctx = getContext();
  if (!ctx) return;
  const startDelay = spec.delayMs ? spec.delayMs / 1000 : 0;
  renderTone(ctx, spec, ctx.currentTime + startDelay);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Short hover tick. Pass the active theme to apply its profile. */
export function playHover(theme?: ChatTheme | null): void {
  play(getProfile(theme).hover);
}

/** Click chirp. Pass the active theme to apply its profile. */
export function playClick(theme?: ChatTheme | null): void {
  play(getProfile(theme).click);
}

/** Subtle keystroke tick. Pass the active theme to apply its profile. */
export function playKeystroke(theme?: ChatTheme | null): void {
  play(getProfile(theme).keystroke);
}

/** Low buzz for errors. Pass the active theme to apply its profile. */
export function playError(theme?: ChatTheme | null): void {
  play(getProfile(theme).error);
}
