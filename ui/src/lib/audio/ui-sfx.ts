"use client";

// Simple global audio context
let audioCtx: AudioContext | null = null;

function getContext() {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

/** 
 * Play a short, high-pitched tick on hover. 
 */
export function playHover() {
  const ctx = getContext();
  if (!ctx) return;
  const t = ctx.currentTime;
  
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc.type = "sine";
  osc.frequency.setValueAtTime(1200, t);
  osc.frequency.exponentialRampToValueAtTime(800, t + 0.05);
  
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(0.05, t + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
  
  osc.connect(gain);
  gain.connect(ctx.destination);
  
  osc.start(t);
  osc.stop(t + 0.05);
}

/** 
 * Play a solid chirp for clicks.
 */
export function playClick() {
  const ctx = getContext();
  if (!ctx) return;
  const t = ctx.currentTime;
  
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc.type = "square";
  // Chirp down quickly
  osc.frequency.setValueAtTime(800, t);
  osc.frequency.exponentialRampToValueAtTime(300, t + 0.1);
  
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(0.1, t + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
  
  osc.connect(gain);
  gain.connect(ctx.destination);
  
  osc.start(t);
  osc.stop(t + 0.1);
}

/** 
 * Play a very subtle mechanical tick for typing.
 */
export function playKeystroke() {
  const ctx = getContext();
  if (!ctx) return;
  const t = ctx.currentTime;
  
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc.type = "triangle";
  // Slight randomization to sound mechanical
  const baseFreq = 400 + Math.random() * 200;
  osc.frequency.setValueAtTime(baseFreq, t);
  osc.frequency.exponentialRampToValueAtTime(100, t + 0.03);
  
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(0.03, t + 0.005);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.03);
  
  osc.connect(gain);
  gain.connect(ctx.destination);
  
  osc.start(t);
  osc.stop(t + 0.03);
}

/**
 * Low pitched buzz for errors.
 */
export function playError() {
  const ctx = getContext();
  if (!ctx) return;
  const t = ctx.currentTime;
  
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(150, t);
  osc.frequency.linearRampToValueAtTime(100, t + 0.2);
  
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(0.1, t + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
  
  osc.connect(gain);
  gain.connect(ctx.destination);
  
  osc.start(t);
  osc.stop(t + 0.2);
}
