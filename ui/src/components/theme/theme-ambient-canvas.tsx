"use client";

import { useEffect, useRef } from "react";
import { useSettingsStore } from "@/lib/stores/settings-store";

// Sidebar pixel widths — must match Tailwind classes in app-shell.tsx
const SW_FULL  = 256; // w-64
const SW_SLIM  =  56; // w-14
const SW_NONE  =   0;

// ─────────────────────────────────────────────────────────────
//  Types
// ─────────────────────────────────────────────────────────────
interface Stream {
  x: number; y: number;
  dir: "h" | "v";
  speed: number;
  len: number;
  opacity: number;
  age: number;
  maxAge: number;
}

interface Glyph {
  col: number;
  y: number;
  speed: number;
  char: string;
  opacity: number;
  bright: boolean;
}

interface Rune {
  x: number; y: number;
  r: number;
  age: number;
  maxAge: number;
  spin: number;
}

interface Star {
  x: number; y: number;
  r: number;
  speed: number;
}

interface SandParticle {
  x: number; y: number;
  vx: number; vy: number;
  r: number;
  opacity: number;
  life: number;
  maxLife: number;
}

interface CanvasState {
  streams: Stream[];
  lastStreamSpawn: number;
  glyphs: Glyph[];
  runes: Rune[];
  lastRuneSpawn: number;
  stars: Star[];
  sand: SandParticle[];
}

function mkState(): CanvasState {
  return {
    streams: [], lastStreamSpawn: 0,
    glyphs: [],
    runes: [], lastRuneSpawn: 0,
    stars: [],
    sand: [],
  };
}

// ─────────────────────────────────────────────────────────────
//  HAL 9000 — breathing iris with rotating petals
// ─────────────────────────────────────────────────────────────
function drawHAL(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, sw: number) {
  ctx.clearRect(0, 0, w, h);

  const cx = sw + (w - sw) * 0.5;
  const cy = h * 0.44;

  const breathe = 0.93 + Math.sin(t * 0.0007) * 0.07;
  const slowSpin = t * 0.00005;
  const fastSpin = t * 0.00012;

  // Outer ambient field
  const ambient = ctx.createRadialGradient(cx, cy, 100, cx, cy, 420);
  ambient.addColorStop(0, `rgba(160,0,0,${0.10 + Math.sin(t * 0.0008) * 0.04})`);
  ambient.addColorStop(0.5, `rgba(80,0,0,0.04)`);
  ambient.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath(); ctx.arc(cx, cy, 420, 0, Math.PI * 2);
  ctx.fillStyle = ambient; ctx.fill();

  // Concentric rings
  [280, 230, 185, 145, 110, 78, 52, 33, 20].forEach((r, i) => {
    const a = 0.05 + i * 0.012 + Math.sin(t * 0.001 + i * 0.4) * 0.03;
    ctx.beginPath(); ctx.arc(cx, cy, r * breathe, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(200,0,0,${a})`;
    ctx.lineWidth = i === 0 ? 1.5 : 1; ctx.stroke();
  });

  // Rotating sector ring
  for (let i = 0; i < 16; i++) {
    const angle = slowSpin + (i / 16) * Math.PI * 2;
    const pulse = 0.06 + Math.sin(t * 0.0015 + i * 0.8) * 0.04;
    ctx.beginPath();
    ctx.arc(cx, cy, 235 * breathe, angle, angle + (Math.PI * 2) / 16 - 0.04);
    ctx.strokeStyle = `rgba(180,0,0,${pulse})`;
    ctx.lineWidth = 10; ctx.stroke();
  }

  // Iris petals
  for (let i = 0; i < 18; i++) {
    const angle = fastSpin + (i / 18) * Math.PI * 2;
    const innerR = 30 * breathe, outerR = 105 * breathe, spread = 0.15;
    const brightness = 0.05 + Math.sin(t * 0.002 + i * 0.7) * 0.03;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle - spread) * innerR, cy + Math.sin(angle - spread) * innerR);
    ctx.lineTo(cx + Math.cos(angle) * outerR, cy + Math.sin(angle) * outerR);
    ctx.lineTo(cx + Math.cos(angle + spread) * innerR, cy + Math.sin(angle + spread) * innerR);
    ctx.closePath();
    ctx.fillStyle = `rgba(150,0,0,${brightness})`; ctx.fill();
  }

  // Scan line
  const scanAngle = t * 0.0006;
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(scanAngle);
  const scanGrad = ctx.createLinearGradient(0, 0, 180 * breathe, 0);
  scanGrad.addColorStop(0, "rgba(220,0,0,0)");
  scanGrad.addColorStop(0.6, `rgba(220,0,0,${0.08 + Math.sin(t * 0.001) * 0.04})`);
  scanGrad.addColorStop(1, "rgba(220,0,0,0)");
  ctx.beginPath();
  ctx.moveTo(0, -1.5); ctx.lineTo(180 * breathe, -1.5);
  ctx.lineTo(180 * breathe, 1.5); ctx.lineTo(0, 1.5); ctx.closePath();
  ctx.fillStyle = scanGrad; ctx.fill();
  ctx.restore();

  // Core pupil
  const coreIntensity = 0.5 + Math.sin(t * 0.001) * 0.18;
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, 22 * breathe);
  core.addColorStop(0, `rgba(255,230,210,${coreIntensity})`);
  core.addColorStop(0.25, `rgba(255,40,20,${coreIntensity * 0.7})`);
  core.addColorStop(0.6, `rgba(160,0,0,${coreIntensity * 0.3})`);
  core.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath(); ctx.arc(cx, cy, 22 * breathe, 0, Math.PI * 2);
  ctx.fillStyle = core; ctx.fill();

  ctx.beginPath(); ctx.arc(cx, cy, 18 * breathe, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(255,100,80,${0.15 + Math.sin(t * 0.001) * 0.1})`;
  ctx.lineWidth = 2; ctx.stroke();
}

// ─────────────────────────────────────────────────────────────
//  TRON — The Grid with live light-cycle streams
// ─────────────────────────────────────────────────────────────
function spawnStream(w: number, h: number, sidebarW: number): Stream {
  const dir: "h" | "v" = Math.random() > 0.5 ? "h" : "v";
  const G = 48;
  const snap = (v: number) => Math.round(v / G) * G;
  if (dir === "h") {
    const forward = Math.random() > 0.5;
    return {
      dir, speed: (Math.random() * 2.5 + 2) * (forward ? 1 : -1),
      x: forward ? sidebarW : w,
      y: snap(Math.random() * h),
      len: (Math.floor(Math.random() * 8) + 5) * G,
      opacity: 0.5 + Math.random() * 0.5,
      age: 0, maxAge: 2000 + Math.random() * 2500,
    };
  } else {
    const forward = Math.random() > 0.5;
    return {
      dir, speed: (Math.random() * 2.5 + 2) * (forward ? 1 : -1),
      x: snap(sidebarW + Math.random() * (w - sidebarW)),
      y: forward ? 0 : h,
      len: (Math.floor(Math.random() * 6) + 4) * G,
      opacity: 0.5 + Math.random() * 0.5,
      age: 0, maxAge: 2000 + Math.random() * 2500,
    };
  }
}

function drawTron(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, state: CanvasState, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const G = 48, sidebarW = sw;
  const cyan = (a: number) => `rgba(0,240,255,${a})`;
  const white = (a: number) => `rgba(200,255,255,${a})`;
  const fadeW = G * 2;

  // Grid with left-edge fade
  ctx.lineWidth = 0.5;
  for (let x = sidebarW; x <= w; x += G) {
    const edgeFade = Math.min(1, (x - sidebarW) / fadeW);
    const base = (0.055 + Math.sin(t * 0.001 + x * 0.008) * 0.015) * edgeFade;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h);
    ctx.strokeStyle = cyan(base); ctx.stroke();
  }
  for (let y = 0; y <= h; y += G) {
    const hGrad = ctx.createLinearGradient(sidebarW, y, sidebarW + fadeW, y);
    const base = 0.055 + Math.sin(t * 0.001 + y * 0.008) * 0.015;
    hGrad.addColorStop(0, cyan(0)); hGrad.addColorStop(1, cyan(base));
    ctx.beginPath(); ctx.moveTo(sidebarW, y); ctx.lineTo(w, y);
    ctx.strokeStyle = hGrad; ctx.stroke();
  }

  // Intersection flares
  for (let x = sidebarW; x <= w; x += G) {
    for (let y = 0; y <= h; y += G) {
      const pulse = Math.sin(t * 0.0025 + x * 0.05 + y * 0.05);
      if (pulse > 0.72) {
        const a = (pulse - 0.72) * 1.0;
        ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fillStyle = cyan(a); ctx.fill();
      }
    }
  }

  // Spawn + draw light streams
  if (t - state.lastStreamSpawn > 350 && state.streams.length < 16) {
    state.streams.push(spawnStream(w, h, sidebarW));
    state.lastStreamSpawn = t;
  }
  state.streams = state.streams.filter(s => s.age < s.maxAge);
  state.streams.forEach(s => {
    s.age += 16;
    const fade = Math.sin((s.age / s.maxAge) * Math.PI);
    const pos = (s.dir === "h" ? s.x : s.y) + s.speed * (s.age / 16) * 0.8;
    const tail = pos - s.len * Math.sign(s.speed);
    ctx.shadowBlur = 12; ctx.shadowColor = cyan(0.9); ctx.lineWidth = 2;
    if (s.dir === "h") {
      const g = ctx.createLinearGradient(tail, 0, pos, 0);
      g.addColorStop(0, cyan(0)); g.addColorStop(0.7, cyan(0.25 * fade * s.opacity)); g.addColorStop(1, white(0.95 * fade * s.opacity));
      ctx.beginPath(); ctx.moveTo(tail, s.y); ctx.lineTo(pos, s.y); ctx.strokeStyle = g; ctx.stroke();
      ctx.beginPath(); ctx.arc(pos, s.y, 3.5, 0, Math.PI * 2); ctx.fillStyle = white(fade * s.opacity); ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = cyan(0.2 * fade * s.opacity);
      ctx.beginPath(); ctx.moveTo(pos, s.y - G * 0.4); ctx.lineTo(pos, s.y - 2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pos, s.y + 2); ctx.lineTo(pos, s.y + G * 0.4); ctx.stroke();
    } else {
      const g = ctx.createLinearGradient(0, tail, 0, pos);
      g.addColorStop(0, cyan(0)); g.addColorStop(0.7, cyan(0.25 * fade * s.opacity)); g.addColorStop(1, white(0.95 * fade * s.opacity));
      ctx.beginPath(); ctx.moveTo(s.x, tail); ctx.lineTo(s.x, pos); ctx.strokeStyle = g; ctx.stroke();
      ctx.beginPath(); ctx.arc(s.x, pos, 3.5, 0, Math.PI * 2); ctx.fillStyle = white(fade * s.opacity); ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = cyan(0.2 * fade * s.opacity);
      ctx.beginPath(); ctx.moveTo(s.x - G * 0.4, pos); ctx.lineTo(s.x - 2, pos); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(s.x + 2, pos); ctx.lineTo(s.x + G * 0.4, pos); ctx.stroke();
    }
    ctx.shadowBlur = 0;
  });

  // Sidebar edge circuit trace
  const traceY = (t * 0.08) % h;
  const traceH = 100, traceX = sidebarW + 1;
  const traceGrad = ctx.createLinearGradient(0, traceY - traceH, 0, traceY + traceH);
  traceGrad.addColorStop(0, cyan(0)); traceGrad.addColorStop(0.5, cyan(0.55)); traceGrad.addColorStop(1, cyan(0));
  ctx.lineWidth = 1; ctx.shadowBlur = 6; ctx.shadowColor = cyan(1);
  ctx.beginPath(); ctx.moveTo(traceX, traceY - traceH); ctx.lineTo(traceX, traceY + traceH);
  ctx.strokeStyle = traceGrad; ctx.stroke();
  ctx.shadowBlur = 0;
}

// ─────────────────────────────────────────────────────────────
//  BLADE RUNNER — Voigt-Kampff iris analyzer
// ─────────────────────────────────────────────────────────────
function drawBladeRunner(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const chatW = w - sw;
  const amber = (a: number) => `rgba(220,148,14,${a})`;
  const dimAmber = (a: number) => `rgba(160,90,5,${a})`;

  // VK iris centered in chat area
  const ix = sw + chatW * 0.5;
  const iy = h * 0.40;
  const iR = Math.min(chatW * 0.32, 240);
  const iBreath = 0.95 + Math.sin(t * 0.0009) * 0.05;
  const iSpin = t * 0.00018;

  // Outer glow
  const outerGlow = ctx.createRadialGradient(ix, iy, iR * 0.5, ix, iy, iR * 1.8);
  outerGlow.addColorStop(0, amber(0.08)); outerGlow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath(); ctx.arc(ix, iy, iR * 1.8, 0, Math.PI * 2);
  ctx.fillStyle = outerGlow; ctx.fill();

  // Concentric measurement rings
  [1.0, 0.82, 0.65, 0.50, 0.36, 0.24, 0.14].forEach((scale, i) => {
    ctx.beginPath(); ctx.arc(ix, iy, iR * scale * iBreath, 0, Math.PI * 2);
    const a = 0.22 + i * 0.10 + Math.sin(t * 0.001 + i * 0.5) * 0.05;
    ctx.strokeStyle = amber(a); ctx.lineWidth = i === 0 ? 2 : 1; ctx.stroke();
    if (i === 0) {
      for (let tick = 0; tick < 36; tick++) {
        const ang = (tick / 36) * Math.PI * 2;
        const r1 = iR * 0.96, r2 = iR * 1.0;
        ctx.beginPath();
        ctx.moveTo(ix + Math.cos(ang) * r1, iy + Math.sin(ang) * r1);
        ctx.lineTo(ix + Math.cos(ang) * r2, iy + Math.sin(ang) * r2);
        ctx.strokeStyle = amber(0.4); ctx.lineWidth = tick % 9 === 0 ? 1.5 : 0.5; ctx.stroke();
      }
    }
  });

  // Iris petals
  for (let i = 0; i < 14; i++) {
    const ang = iSpin + (i / 14) * Math.PI * 2;
    const r1 = iR * 0.18 * iBreath, r2 = iR * 0.52 * iBreath, spread = 0.18;
    const brightness = 0.18 + Math.sin(t * 0.0018 + i * 0.9) * 0.08;
    ctx.beginPath();
    ctx.moveTo(ix + Math.cos(ang - spread) * r1, iy + Math.sin(ang - spread) * r1);
    ctx.lineTo(ix + Math.cos(ang) * r2, iy + Math.sin(ang) * r2);
    ctx.lineTo(ix + Math.cos(ang + spread) * r1, iy + Math.sin(ang + spread) * r1);
    ctx.closePath(); ctx.fillStyle = amber(brightness); ctx.fill();
  }

  // Rotating reticle
  const reticleAngle = t * 0.0004;
  const rx1 = ix + Math.cos(reticleAngle) * iR * 0.72, ry1 = iy + Math.sin(reticleAngle) * iR * 0.72;
  const rx2 = ix + Math.cos(reticleAngle + Math.PI) * iR * 0.72, ry2 = iy + Math.sin(reticleAngle + Math.PI) * iR * 0.72;
  ctx.beginPath(); ctx.moveTo(rx1, ry1); ctx.lineTo(rx2, ry2);
  ctx.strokeStyle = amber(0.55); ctx.lineWidth = 1; ctx.stroke();
  const bSize = 7;
  [[rx1, ry1], [rx2, ry2]].forEach(([bx, by]) => {
    const perp = reticleAngle + Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(bx + Math.cos(perp) * bSize, by + Math.sin(perp) * bSize);
    ctx.lineTo(bx, by);
    ctx.lineTo(bx - Math.cos(perp) * bSize, by - Math.sin(perp) * bSize);
    ctx.strokeStyle = amber(0.6); ctx.lineWidth = 1; ctx.stroke();
  });

  // Pupil
  ctx.beginPath(); ctx.arc(ix, iy, iR * 0.12 * iBreath, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(0,0,0,0.9)"; ctx.fill();
  ctx.strokeStyle = amber(0.5); ctx.lineWidth = 1; ctx.stroke();

  // Oscilloscope in sidebar — hairline separator + floating waveform
  const oscX = 10, oscW = sw - 20, oscY = h - 70, oscH = 40;
  const points = 60;
  const sepY = oscY - oscH - 8;
  const sepGrad = ctx.createLinearGradient(oscX, sepY, oscX + oscW, sepY);
  sepGrad.addColorStop(0, amber(0)); sepGrad.addColorStop(0.2, amber(0.28));
  sepGrad.addColorStop(0.8, amber(0.28)); sepGrad.addColorStop(1, amber(0));
  ctx.beginPath(); ctx.moveTo(oscX, sepY); ctx.lineTo(oscX + oscW, sepY);
  ctx.strokeStyle = sepGrad; ctx.lineWidth = 0.75; ctx.stroke();
  ctx.font = "8px 'JetBrains Mono', monospace";
  ctx.fillStyle = amber(0.38); ctx.fillText("EMOTIONAL RESPONSE", oscX + 4, oscY - oscH + 2);
  ctx.fillStyle = amber(0.20); ctx.fillText("VK-VI REPLICANT ANALYSIS", oscX + 4, oscY - oscH + 12);

  ctx.beginPath();
  for (let i = 0; i <= points; i++) {
    const px = oscX + (i / points) * oscW;
    const wave = Math.sin(i * 0.18 + t * 0.003) * 0.4 + Math.sin(i * 0.42 + t * 0.002) * 0.25
               + Math.sin(i * 0.09 + t * 0.004) * 0.2 + Math.sin(i * 0.7 + t * 0.006) * 0.08;
    const py = oscY - oscH * 0.5 - wave * oscH * 0.38;
    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
  }
  ctx.strokeStyle = amber(0.65); ctx.lineWidth = 1.2;
  ctx.shadowBlur = 6; ctx.shadowColor = amber(0.8);
  ctx.stroke(); ctx.shadowBlur = 0;

  const cursorX = oscX + ((t * 0.04) % oscW);
  ctx.beginPath(); ctx.moveTo(cursorX, oscY - oscH - 4); ctx.lineTo(cursorX, oscY + 4);
  ctx.strokeStyle = amber(0.35); ctx.lineWidth = 1; ctx.stroke();

  // Ambient city glow
  const horizon = ctx.createLinearGradient(sw, h * 0.7, sw, h);
  horizon.addColorStop(0, "rgba(0,0,0,0)");
  horizon.addColorStop(0.5, dimAmber(0.06)); horizon.addColorStop(1, dimAmber(0.14));
  ctx.fillStyle = horizon; ctx.fillRect(sw, h * 0.7, chatW, h * 0.3);
}

// ─────────────────────────────────────────────────────────────
//  SHADOWRUN — Awakened AR / matrix rain + runes
// ─────────────────────────────────────────────────────────────
const SR_GLYPHS = "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ01";
const SR_RUNE_CHARS = "ᚠᚡᚢᚣᚤᚥᚦᚧᚨᚩᚪᚫᚬᚭᚮᚯᚰᚱᚲᚳᚴᚵᚶᚷᚸᚹᚺᚻᚼᚽᚾᚿᛀᛁᛂᛃᛄᛅᛆᛇᛈᛉᛊᛋᛌᛍᛎᛏᛐᛑᛒᛓ";

function initShadowrunGlyphs(w: number, h: number, sw: number, state: CanvasState) {
  const cols = Math.floor(w / 14);
  state.glyphs = Array.from({ length: cols * 3 }, () => ({
    col: Math.floor(Math.random() * cols),
    y: Math.random() * h,
    speed: Math.random() * 1.8 + 0.8,
    char: SR_GLYPHS[Math.floor(Math.random() * SR_GLYPHS.length)],
    opacity: Math.random() * 0.7 + 0.1,
    bright: Math.random() < 0.08,
  }));
}

function drawShadowrun(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, state: CanvasState, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const sidebarW = sw;
  const teal = (a: number) => `rgba(0,221,192,${a})`;
  const purple = (a: number) => `rgba(180,60,255,${a})`;

  if (state.glyphs.length < 40) initShadowrunGlyphs(w, h, sw, state);
  const colW = 14;

  state.glyphs.forEach(g => {
    if (Math.random() < 0.002) g.char = SR_GLYPHS[Math.floor(Math.random() * SR_GLYPHS.length)];
    g.y += g.speed;
    if (g.y > h + 20) {
      g.y = -20;
      g.col = Math.floor(Math.random() * Math.floor(w / colW));
      g.speed = Math.random() * 1.8 + 0.8;
      g.bright = Math.random() < 0.08;
    }
    const x = g.col * colW;
    if (x < sidebarW) return;
    ctx.font = `${colW - 2}px monospace`;
    ctx.fillStyle = teal(g.bright ? g.opacity * 0.3 : g.opacity * 0.12);
    ctx.fillText(g.char, x, g.y - colW);
    ctx.fillStyle = teal(g.bright ? g.opacity * 0.6 : g.opacity * 0.2);
    ctx.fillText(g.char, x, g.y);
    if (g.bright) { ctx.fillStyle = "rgba(200,255,250,0.9)"; }
    else { ctx.fillStyle = g.col % 7 === 0 ? purple(g.opacity * 0.55) : teal(g.opacity * 0.42); }
    ctx.fillText(g.char, x, g.y + colW * 0.5);
  });

  // Awakened rune circles
  if (t - state.lastRuneSpawn > 4000 && state.runes.length < 4) {
    state.lastRuneSpawn = t;
    const margin = 120;
    state.runes.push({
      x: sidebarW + margin + Math.random() * (w - sidebarW - margin * 2),
      y: margin + Math.random() * (h - margin * 2),
      r: 60 + Math.random() * 50,
      age: 0, maxAge: 6000 + Math.random() * 4000,
      spin: (Math.random() - 0.5) * 0.0003,
    });
  }
  state.runes = state.runes.filter(r => r.age < r.maxAge);
  state.runes.forEach(rune => {
    rune.age += 16;
    const fade = Math.sin((rune.age / rune.maxAge) * Math.PI);
    ctx.save(); ctx.translate(rune.x, rune.y); ctx.rotate(rune.spin * rune.age);
    ctx.beginPath(); ctx.arc(0, 0, rune.r, 0, Math.PI * 2);
    ctx.strokeStyle = purple(0.25 * fade); ctx.lineWidth = 1; ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, rune.r * 0.7, 0, Math.PI * 2);
    ctx.strokeStyle = teal(0.18 * fade); ctx.lineWidth = 0.75; ctx.stroke();
    const numChars = 8;
    ctx.font = `${Math.floor(rune.r * 0.22)}px serif`;
    for (let i = 0; i < numChars; i++) {
      const ang = (i / numChars) * Math.PI * 2 - Math.PI / 2;
      const cx = Math.cos(ang) * rune.r * 0.85, cy = Math.sin(ang) * rune.r * 0.85;
      const char = SR_RUNE_CHARS[Math.floor((rune.age * 0.001 + i * 3) % SR_RUNE_CHARS.length)];
      ctx.fillStyle = teal(0.35 * fade); ctx.fillText(char, cx - 5, cy + 5);
    }
    ctx.lineWidth = 0.5; ctx.strokeStyle = purple(0.18 * fade);
    [[0, -rune.r, 0, rune.r], [-rune.r, 0, rune.r, 0]].forEach(([x1, y1, x2, y2]) => {
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    });
    ctx.restore();
  });

  // AR brackets on sidebar
  const bracketOpacity = 0.12 + Math.sin(t * 0.002) * 0.04;
  const bx = 8, bw = sidebarW - 16, by = h * 0.18, bh = h * 0.56, bs = 16;
  ctx.lineWidth = 1; ctx.strokeStyle = teal(bracketOpacity);
  ctx.beginPath(); ctx.moveTo(bx + bs, by); ctx.lineTo(bx, by); ctx.lineTo(bx, by + bs); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(bx + bw - bs, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + bs); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(bx + bs, by + bh); ctx.lineTo(bx, by + bh); ctx.lineTo(bx, by + bh - bs); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(bx + bw - bs, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - bs); ctx.stroke();

  // Sidebar neon edge pulse
  const edgeGrad = ctx.createLinearGradient(0, 0, 0, h);
  const pulsePos = (t * 0.06) % (h + 200) - 100;
  edgeGrad.addColorStop(0, teal(0));
  const p1 = Math.max(0, Math.min(1, (pulsePos - 80) / h));
  const p2 = Math.max(0, Math.min(1, pulsePos / h));
  const p3 = Math.max(0, Math.min(1, (pulsePos + 80) / h));
  edgeGrad.addColorStop(p1, teal(0.05));
  edgeGrad.addColorStop(p2, teal(0.7));
  edgeGrad.addColorStop(p3, teal(0.05));
  edgeGrad.addColorStop(1, teal(0));
  ctx.lineWidth = 1.5; ctx.strokeStyle = edgeGrad;
  ctx.shadowBlur = 10; ctx.shadowColor = teal(1);
  ctx.beginPath(); ctx.moveTo(sidebarW, 0); ctx.lineTo(sidebarW, h);
  ctx.stroke(); ctx.shadowBlur = 0;
}

// ─────────────────────────────────────────────────────────────
//  NOSTROMO — MU/TH/UR motion tracker
// ─────────────────────────────────────────────────────────────
function drawNostromo(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const amber = (a: number) => `rgba(255,140,0,${a})`;

  // Motion tracker centered in sidebar lower half
  const mx = sw * 0.5;
  const my = h * 0.58;
  const mr = Math.min(sw * 0.40, 95);

  // Concentric rings
  [1.0, 0.75, 0.5, 0.25].forEach((scale, i) => {
    ctx.beginPath(); ctx.arc(mx, my, mr * scale, 0, Math.PI * 2);
    ctx.strokeStyle = amber(0.18 + i * 0.04);
    ctx.lineWidth = i === 0 ? 1.5 : 0.75; ctx.stroke();
  });

  // Cross-hairs
  ctx.lineWidth = 0.5; ctx.strokeStyle = amber(0.09);
  [[mx - mr, my, mx + mr, my], [mx, my - mr, mx, my + mr]].forEach(([x1, y1, x2, y2]) => {
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  });

  // Radar sweep with trail
  const sweepAngle = (t * 0.0009) % (Math.PI * 2);
  const trailLen = Math.PI / 5;
  for (let i = 0; i < 28; i++) {
    const ang = sweepAngle - (i / 28) * trailLen;
    ctx.beginPath(); ctx.moveTo(mx, my);
    ctx.lineTo(mx + Math.cos(ang) * mr, my + Math.sin(ang) * mr);
    ctx.strokeStyle = amber((1 - i / 28) * 0.13);
    ctx.lineWidth = 5; ctx.stroke();
  }
  ctx.beginPath(); ctx.moveTo(mx, my);
  ctx.lineTo(mx + Math.cos(sweepAngle) * mr, my + Math.sin(sweepAngle) * mr);
  ctx.strokeStyle = amber(0.75); ctx.lineWidth = 1.5;
  ctx.shadowBlur = 8; ctx.shadowColor = amber(1); ctx.stroke(); ctx.shadowBlur = 0;

  // Blip contacts — fade in when sweep passes each fixed position
  const blipAngles = [0.6, 1.8, 3.2, 4.1, 5.3];
  const blipDists  = [0.45, 0.70, 0.30, 0.62, 0.82];
  blipAngles.forEach((ba, i) => {
    const angDiff = ((sweepAngle - ba) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    const fade = Math.max(0, 1 - angDiff / (Math.PI * 0.85));
    if (fade < 0.02) return;
    const bx = mx + Math.cos(ba) * blipDists[i] * mr;
    const by = my + Math.sin(ba) * blipDists[i] * mr;
    ctx.beginPath(); ctx.arc(bx, by, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = amber(fade * 0.9);
    ctx.shadowBlur = 8; ctx.shadowColor = amber(1); ctx.fill(); ctx.shadowBlur = 0;
  });

  // MU/TH/UR readout labels
  ctx.font = "7px 'JetBrains Mono', monospace";
  ctx.fillStyle = amber(0.40);
  ctx.fillText("MOTION TRACKER", mx - 40, my - mr - 8);
  ctx.fillStyle = amber(0.22);
  const range = Math.floor(40 + Math.sin(t * 0.0003) * 8);
  ctx.fillText(`RANGE: ${range}m`, mx - 24, my + mr + 16);
  ctx.fillStyle = amber(0.15);
  const contacts = blipAngles.filter((ba) => {
    const ad = ((sweepAngle - ba) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    return ad < Math.PI * 0.85;
  }).length;
  ctx.fillText(`CONTACTS: ${contacts}`, mx - 28, my + mr + 28);

  // CRT amber scanlines across chat area
  const chatW = w - sw;
  for (let y = 0; y < h; y += 4) {
    ctx.fillStyle = amber(0.012);
    ctx.fillRect(sw, y, chatW, 1);
  }

  // Slow amber scan bar drifting down chat
  const scanY = (t * 0.025) % h;
  const scanGrad = ctx.createLinearGradient(sw, scanY - 60, sw, scanY + 60);
  scanGrad.addColorStop(0, "rgba(255,140,0,0)");
  scanGrad.addColorStop(0.5, "rgba(255,140,0,0.04)");
  scanGrad.addColorStop(1, "rgba(255,140,0,0)");
  ctx.fillStyle = scanGrad; ctx.fillRect(sw, scanY - 60, chatW, 120);
}

// ─────────────────────────────────────────────────────────────
//  TERMINAL — phosphor CRT with ASCII rain
// ─────────────────────────────────────────────────────────────
const TERM_GLYPHS = "0123456789ABCDEF><[]{}|/\\!@#$%^&*_+=?:;.,~`'\"";

function initTerminalGlyphs(w: number, h: number, sw: number, state: CanvasState) {
  const chatW = w - sw;
  const cols = Math.floor(chatW / 14);
  state.glyphs = Array.from({ length: cols * 2 }, () => ({
    col: Math.floor(Math.random() * cols),
    y: Math.random() * h,
    speed: Math.random() * 0.9 + 0.3,
    char: TERM_GLYPHS[Math.floor(Math.random() * TERM_GLYPHS.length)],
    opacity: Math.random() * 0.5 + 0.1,
    bright: Math.random() < 0.04,
  }));
}

function drawTerminal(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, state: CanvasState, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const chatW = w - sw;
  const green = (a: number) => `rgba(51,255,102,${a})`;
  const colW = 14;

  if (state.glyphs.length < 20) initTerminalGlyphs(w, h, sw, state);

  state.glyphs.forEach(g => {
    if (Math.random() < 0.001) g.char = TERM_GLYPHS[Math.floor(Math.random() * TERM_GLYPHS.length)];
    g.y += g.speed;
    if (g.y > h + 20) {
      g.y = -20;
      g.col = Math.floor(Math.random() * Math.floor(chatW / colW));
      g.bright = Math.random() < 0.04;
    }
    const x = sw + g.col * colW;
    ctx.font = `${colW - 2}px 'JetBrains Mono', monospace`;
    ctx.fillStyle = green(g.bright ? g.opacity * 0.4 : g.opacity * 0.12);
    ctx.fillText(g.char, x, g.y - colW);
    ctx.fillStyle = green(g.bright ? g.opacity * 0.8 : g.opacity * 0.22);
    ctx.fillText(g.char, x, g.y);
    if (g.bright) {
      ctx.fillStyle = "rgba(180,255,200,0.9)";
      ctx.shadowBlur = 6; ctx.shadowColor = green(1);
    } else {
      ctx.fillStyle = green(g.opacity * 0.45);
    }
    ctx.fillText(g.char, x, g.y + colW * 0.5);
    ctx.shadowBlur = 0;
  });

  // Horizontal CRT scanline sweep
  const scanY = (t * 0.05) % h;
  const scanGrad = ctx.createLinearGradient(sw, scanY - 40, sw, scanY + 40);
  scanGrad.addColorStop(0, green(0)); scanGrad.addColorStop(0.5, green(0.055)); scanGrad.addColorStop(1, green(0));
  ctx.fillStyle = scanGrad; ctx.fillRect(sw, scanY - 40, chatW, 80);

  // CRT left/right edge vignette
  const vgL = ctx.createLinearGradient(sw, 0, sw + 50, 0);
  vgL.addColorStop(0, "rgba(0,0,0,0.20)"); vgL.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = vgL; ctx.fillRect(sw, 0, 50, h);
  const vgR = ctx.createLinearGradient(w - 50, 0, w, 0);
  vgR.addColorStop(0, "rgba(0,0,0,0)"); vgR.addColorStop(1, "rgba(0,0,0,0.20)");
  ctx.fillStyle = vgR; ctx.fillRect(w - 50, 0, 50, h);

  // Sidebar: vertical phosphor pulse
  const sidebarPulseY = (t * 0.045) % h;
  const spGrad = ctx.createLinearGradient(0, sidebarPulseY - 80, 0, sidebarPulseY + 80);
  spGrad.addColorStop(0, green(0)); spGrad.addColorStop(0.5, green(0.12)); spGrad.addColorStop(1, green(0));
  ctx.fillStyle = spGrad; ctx.fillRect(0, sidebarPulseY - 80, sw, 160);
}

// ─────────────────────────────────────────────────────────────
//  OPS — Mission Control tactical scope + orbital arcs
// ─────────────────────────────────────────────────────────────
function drawOps(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const chatW = w - sw;
  const blue = (a: number) => `rgba(76,159,232,${a})`;
  const cyan2 = (a: number) => `rgba(100,200,255,${a})`;

  // Tactical scope in sidebar
  const rx = sw * 0.5, ry = h * 0.50;
  const rr = Math.min(sw * 0.40, 90);

  [1.0, 0.67, 0.33].forEach((scale, i) => {
    ctx.beginPath(); ctx.arc(rx, ry, rr * scale, 0, Math.PI * 2);
    ctx.strokeStyle = blue(0.18 + i * 0.06); ctx.lineWidth = i === 0 ? 1.5 : 0.75; ctx.stroke();
  });
  ctx.lineWidth = 0.5; ctx.strokeStyle = blue(0.10);
  [[rx - rr, ry, rx + rr, ry], [rx, ry - rr, rx, ry + rr]].forEach(([x1, y1, x2, y2]) => {
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  });

  // Radar sweep
  const sweepAngle = (t * 0.0006) % (Math.PI * 2);
  for (let i = 0; i < 28; i++) {
    const ang = sweepAngle - (i / 28) * (Math.PI / 5);
    ctx.beginPath(); ctx.moveTo(rx, ry);
    ctx.lineTo(rx + Math.cos(ang) * rr, ry + Math.sin(ang) * rr);
    ctx.strokeStyle = blue((1 - i / 28) * 0.12); ctx.lineWidth = 4; ctx.stroke();
  }
  ctx.beginPath(); ctx.moveTo(rx, ry);
  ctx.lineTo(rx + Math.cos(sweepAngle) * rr, ry + Math.sin(sweepAngle) * rr);
  ctx.strokeStyle = blue(0.75); ctx.lineWidth = 1.5;
  ctx.shadowBlur = 8; ctx.shadowColor = blue(1); ctx.stroke(); ctx.shadowBlur = 0;

  // Scope blip contacts
  const blipAs = [0.9, 2.3, 3.8, 5.0];
  const blipDs = [0.5, 0.72, 0.38, 0.60];
  blipAs.forEach((ba, i) => {
    const ad = ((sweepAngle - ba) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    const fade = Math.max(0, 1 - ad / (Math.PI * 0.9));
    if (fade < 0.02) return;
    ctx.beginPath(); ctx.arc(rx + Math.cos(ba) * blipDs[i] * rr, ry + Math.sin(ba) * blipDs[i] * rr, 3, 0, Math.PI * 2);
    ctx.fillStyle = cyan2(fade * 0.9); ctx.shadowBlur = 6; ctx.shadowColor = cyan2(1); ctx.fill(); ctx.shadowBlur = 0;
  });

  ctx.font = "7px 'JetBrains Mono', monospace";
  ctx.fillStyle = blue(0.40); ctx.fillText("TACTICAL SCOPE", rx - 38, ry - rr - 8);

  // Orbital arcs in chat area
  const ocx = sw + chatW * 0.5, ocy = h * 0.40;
  const orbits = [
    { rx: chatW * 0.44, ry: h * 0.20, speed: 0.00028, nodes: 3, tilt: 0.1 },
    { rx: chatW * 0.33, ry: h * 0.13, speed: 0.00048, nodes: 2, tilt: -0.15 },
    { rx: chatW * 0.20, ry: h * 0.07, speed: 0.00085, nodes: 1, tilt: 0.05 },
  ];

  orbits.forEach((orb, oi) => {
    ctx.beginPath();
    ctx.ellipse(ocx, ocy, orb.rx, orb.ry, orb.tilt, 0, Math.PI * 2);
    ctx.strokeStyle = blue(0.07 + oi * 0.02); ctx.lineWidth = 0.75; ctx.stroke();

    for (let n = 0; n < orb.nodes; n++) {
      const nodeAngle = t * orb.speed + (n / orb.nodes) * Math.PI * 2;
      const nx = ocx + Math.cos(nodeAngle + orb.tilt) * orb.rx;
      const ny = ocy + Math.sin(nodeAngle + orb.tilt) * orb.ry;
      ctx.beginPath(); ctx.arc(nx, ny, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = blue(0.75); ctx.shadowBlur = 8; ctx.shadowColor = blue(1); ctx.fill(); ctx.shadowBlur = 0;
      // Node trail
      for (let tr = 1; tr < 6; tr++) {
        const tAng = nodeAngle - tr * 0.04;
        const tx = ocx + Math.cos(tAng + orb.tilt) * orb.rx;
        const ty = ocy + Math.sin(tAng + orb.tilt) * orb.ry;
        ctx.beginPath(); ctx.arc(tx, ty, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = blue((1 - tr / 6) * 0.3); ctx.fill();
      }
    }
  });

  // Sidebar compass rose under scope
  const crY = ry + rr + 28;
  ctx.font = "7px 'JetBrains Mono', monospace";
  ctx.fillStyle = blue(0.30);
  ctx.fillText("N", rx - 3, crY);
  ctx.fillText(`ALT: ${Math.floor(380 + Math.sin(t * 0.0004) * 12)}km`, rx - 26, crY + 14);
}

// ─────────────────────────────────────────────────────────────
//  LCARS — Deep space starfield with warp streaks
// ─────────────────────────────────────────────────────────────
function initStars(w: number, h: number, state: CanvasState) {
  state.stars = Array.from({ length: 240 }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: Math.random() * 0.8 + 0.1,
    speed: Math.random() * 0.05 + 0.01,
  }));
}

function drawLCARS(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, state: CanvasState, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const chatW = w - sw;

  if (state.stars.length < 100) initStars(w, h, state);

  // Drifting star field
  state.stars.forEach(s => {
    s.x -= s.speed;
    if (s.x < sw - 10) { s.x = w + 5; s.y = Math.random() * h; }
    const brightness = 0.25 + s.r * 0.6 + Math.sin(t * 0.0008 + s.x * 0.01 + s.y * 0.02) * 0.12;
    ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${brightness})`; ctx.fill();
  });

  // Warp streaks — every ~8 seconds a streak fires
  for (let wi = 0; wi < 3; wi++) {
    const warpPeriod = 8000 + wi * 2700;
    const phase = ((t + wi * 2700) % warpPeriod) / warpPeriod;
    if (phase > 0.12) continue;
    const progress = phase / 0.12;
    const seed = Math.floor((t + wi * 2700) / warpPeriod);
    const wy = ((seed * 137 + wi * 53) % 100) / 100 * h * 0.7 + h * 0.15;
    const wLen = 70 + ((seed * 73 + wi * 29) % 100);
    const wx = sw + chatW * (0.3 + ((seed * 97 + wi * 41) % 60) / 100 * 0.5);
    const brightFade = Math.sin(progress * Math.PI);
    const wg = ctx.createLinearGradient(wx - wLen * 0.3, wy, wx + wLen * 0.7, wy);
    wg.addColorStop(0, `rgba(255,255,255,0)`);
    wg.addColorStop(0.3, `rgba(200,220,255,${brightFade * 0.85})`);
    wg.addColorStop(0.7, `rgba(255,255,255,${brightFade * 0.95})`);
    wg.addColorStop(1, `rgba(255,255,255,0)`);
    ctx.strokeStyle = wg; ctx.lineWidth = 1.5;
    ctx.shadowBlur = 10; ctx.shadowColor = "rgba(200,220,255,0.9)";
    ctx.beginPath(); ctx.moveTo(wx - wLen * 0.3, wy); ctx.lineTo(wx + wLen * 0.7, wy);
    ctx.stroke(); ctx.shadowBlur = 0;
  }

  // Faint nebula glow in chat area
  const nebulaGrad = ctx.createRadialGradient(sw + chatW * 0.5, h * 0.4, 0, sw + chatW * 0.5, h * 0.4, chatW * 0.5);
  nebulaGrad.addColorStop(0, `rgba(120,80,180,${0.03 + Math.sin(t * 0.0005) * 0.01})`);
  nebulaGrad.addColorStop(0.6, `rgba(60,40,120,0.02)`);
  nebulaGrad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = nebulaGrad; ctx.fillRect(sw, 0, chatW, h);
}

// ─────────────────────────────────────────────────────────────
//  DUNE — Arrakis sand storm + spice sonar
// ─────────────────────────────────────────────────────────────
function initSandParticles(w: number, h: number, sw: number, state: CanvasState) {
  const chatW = w - sw;
  state.sand = Array.from({ length: 140 }, () => ({
    x: sw + Math.random() * chatW,
    y: Math.random() * h,
    vx: Math.random() * 1.6 + 0.4,
    vy: Math.random() * 0.5 - 0.25,
    r: Math.random() * 1.6 + 0.2,
    opacity: Math.random() * 0.32 + 0.04,
    life: 0,
    maxLife: 8000 + Math.random() * 9000,
  }));
}

function drawDune(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, state: CanvasState, sw: number) {
  ctx.clearRect(0, 0, w, h);
  const chatW = w - sw;
  const sand = (a: number) => `rgba(235,185,80,${a})`;
  const spice = (a: number) => `rgba(200,120,10,${a})`;

  if (state.sand.length < 50) initSandParticles(w, h, sw, state);

  // Flowing sand particles
  state.sand.forEach(p => {
    p.x += p.vx; p.y += p.vy; p.life += 16;
    if (p.x > w + 10 || p.life > p.maxLife) {
      p.x = sw - 5;
      p.y = Math.random() * h;
      p.vx = Math.random() * 1.6 + 0.4;
      p.vy = Math.random() * 0.5 - 0.25;
      p.life = 0; p.maxLife = 8000 + Math.random() * 9000;
    }
    const fade = Math.sin((p.life / p.maxLife) * Math.PI);
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = p.r > 1.3 ? spice(fade * p.opacity) : sand(fade * p.opacity);
    ctx.fill();
  });

  // Spice sonar expansion rings — worm detection
  const sonarCx = sw + chatW * 0.55, sonarCy = h * 0.58;
  for (let i = 0; i < 5; i++) {
    const phase = ((t * 0.00035 + i * 0.75) % 1);
    const r = phase * chatW * 0.38;
    const alpha = (1 - phase) * 0.20;
    ctx.beginPath(); ctx.arc(sonarCx, sonarCy, r, 0, Math.PI * 2);
    ctx.strokeStyle = spice(alpha); ctx.lineWidth = 1; ctx.stroke();
  }

  // Desert horizon shimmer
  const shimmer = ctx.createLinearGradient(sw, h * 0.70, sw, h);
  shimmer.addColorStop(0, "rgba(0,0,0,0)");
  shimmer.addColorStop(0.5, spice(0.04 + Math.sin(t * 0.0009) * 0.02));
  shimmer.addColorStop(1, spice(0.12 + Math.sin(t * 0.0007) * 0.04));
  ctx.fillStyle = shimmer; ctx.fillRect(sw, h * 0.70, chatW, h * 0.30);

  // Heat haze at top
  const haze = ctx.createLinearGradient(sw, 0, sw, h * 0.18);
  haze.addColorStop(0, sand(0.04 + Math.sin(t * 0.0011) * 0.02));
  haze.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = haze; ctx.fillRect(sw, 0, chatW, h * 0.18);

  // Sidebar: sand drift at bottom
  const sideGrad = ctx.createLinearGradient(0, h * 0.8, 0, h);
  sideGrad.addColorStop(0, "rgba(0,0,0,0)");
  sideGrad.addColorStop(1, spice(0.08));
  ctx.fillStyle = sideGrad; ctx.fillRect(0, h * 0.8, sw, h * 0.2);
}

// ─────────────────────────────────────────────────────────────
//  Component
// ─────────────────────────────────────────────────────────────
const CANVAS_THEMES = new Set([
  "hal9000", "tron", "bladerunner", "shadowrun",
  "nostromo", "terminal", "ops",
  "lcars", "lcars-blue", "lcars-teal",
  "dune",
]);

export function ThemeAmbientCanvas() {
  const theme        = useSettingsStore(s => s.theme);
  const sidebarOpen  = useSettingsStore(s => s.sidebarOpen);
  const sidebarSlim  = useSettingsStore(s => s.sidebarSlim);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef    = useRef<number>(0);
  const stateRef  = useRef<CanvasState>(mkState());
  const swRef     = useRef<number>(SW_FULL);

  useEffect(() => {
    swRef.current = !sidebarOpen ? SW_NONE : sidebarSlim ? SW_SLIM : SW_FULL;
  }, [sidebarOpen, sidebarSlim]);

  useEffect(() => {
    if (!CANVAS_THEMES.has(theme)) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    stateRef.current = mkState();

    const resize = () => {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
      const sw = swRef.current;
      if (theme === "shadowrun") initShadowrunGlyphs(canvas.width, canvas.height, sw, stateRef.current);
      if (theme === "terminal")  initTerminalGlyphs(canvas.width, canvas.height, sw, stateRef.current);
      if (theme === "lcars" || theme === "lcars-blue" || theme === "lcars-teal") initStars(canvas.width, canvas.height, stateRef.current);
      if (theme === "dune")      initSandParticles(canvas.width, canvas.height, sw, stateRef.current);
    };
    resize();
    window.addEventListener("resize", resize);

    let running = true;
    const loop = (ts: number) => {
      if (!running) return;
      const w  = canvas.width, h = canvas.height;
      const sw = swRef.current;
      const state = stateRef.current;

      switch (theme) {
        case "hal9000":    drawHAL(ctx, w, h, ts, sw); break;
        case "tron":       drawTron(ctx, w, h, ts, state, sw); break;
        case "bladerunner": drawBladeRunner(ctx, w, h, ts, sw); break;
        case "shadowrun":  drawShadowrun(ctx, w, h, ts, state, sw); break;
        case "nostromo":   drawNostromo(ctx, w, h, ts, sw); break;
        case "terminal":   drawTerminal(ctx, w, h, ts, state, sw); break;
        case "ops":        drawOps(ctx, w, h, ts, sw); break;
        case "lcars": case "lcars-blue": case "lcars-teal":
          drawLCARS(ctx, w, h, ts, state, sw); break;
        case "dune":       drawDune(ctx, w, h, ts, state, sw); break;
      }
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      running = false;
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [theme]);

  if (!CANVAS_THEMES.has(theme)) return null;

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 2,
        mixBlendMode: "screen",
      }}
      aria-hidden="true"
    />
  );
}
