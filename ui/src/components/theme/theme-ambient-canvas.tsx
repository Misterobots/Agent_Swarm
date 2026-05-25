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

interface CanvasState {
  streams: Stream[];
  lastStreamSpawn: number;
  glyphs: Glyph[];
  runes: Rune[];
  lastRuneSpawn: number;
}

function mkState(): CanvasState {
  return { streams: [], lastStreamSpawn: 0, glyphs: [], runes: [], lastRuneSpawn: 0 };
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

  // ── Outer ambient field ──────────────────────────────────
  const ambient = ctx.createRadialGradient(cx, cy, 100, cx, cy, 420);
  ambient.addColorStop(0, `rgba(160,0,0,${0.10 + Math.sin(t * 0.0008) * 0.04})`);
  ambient.addColorStop(0.5, `rgba(80,0,0,0.04)`);
  ambient.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath();
  ctx.arc(cx, cy, 420, 0, Math.PI * 2);
  ctx.fillStyle = ambient;
  ctx.fill();

  // ── Outer concentric rings ───────────────────────────────
  const rings = [280, 230, 185, 145, 110, 78, 52, 33, 20];
  rings.forEach((r, i) => {
    const a = 0.05 + i * 0.012 + Math.sin(t * 0.001 + i * 0.4) * 0.03;
    ctx.beginPath();
    ctx.arc(cx, cy, r * breathe, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(200,0,0,${a})`;
    ctx.lineWidth = i === 0 ? 1.5 : 1;
    ctx.stroke();
  });

  // ── Rotating outer sector ring (slow) ────────────────────
  const numSectors = 16;
  for (let i = 0; i < numSectors; i++) {
    const angle = slowSpin + (i / numSectors) * Math.PI * 2;
    const pulse = 0.06 + Math.sin(t * 0.0015 + i * 0.8) * 0.04;
    ctx.beginPath();
    ctx.arc(cx, cy, 235 * breathe, angle, angle + (Math.PI * 2) / numSectors - 0.04);
    ctx.strokeStyle = `rgba(180,0,0,${pulse})`;
    ctx.lineWidth = 10;
    ctx.stroke();
  }

  // ── Iris petals (fast spin, inner) ───────────────────────
  const petals = 18;
  for (let i = 0; i < petals; i++) {
    const angle = fastSpin + (i / petals) * Math.PI * 2;
    const innerR = 30 * breathe;
    const outerR = 105 * breathe;
    const spread = 0.15;
    const brightness = 0.05 + Math.sin(t * 0.002 + i * 0.7) * 0.03;

    ctx.beginPath();
    ctx.moveTo(
      cx + Math.cos(angle - spread) * innerR,
      cy + Math.sin(angle - spread) * innerR
    );
    ctx.lineTo(
      cx + Math.cos(angle) * outerR,
      cy + Math.sin(angle) * outerR
    );
    ctx.lineTo(
      cx + Math.cos(angle + spread) * innerR,
      cy + Math.sin(angle + spread) * innerR
    );
    ctx.closePath();
    ctx.fillStyle = `rgba(150,0,0,${brightness})`;
    ctx.fill();
  }

  // ── Scan line sweeping across iris ───────────────────────
  const scanAngle = t * 0.0006;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(scanAngle);
  const scanGrad = ctx.createLinearGradient(0, 0, 180 * breathe, 0);
  scanGrad.addColorStop(0, "rgba(220,0,0,0)");
  scanGrad.addColorStop(0.6, `rgba(220,0,0,${0.08 + Math.sin(t * 0.001) * 0.04})`);
  scanGrad.addColorStop(1, "rgba(220,0,0,0)");
  ctx.beginPath();
  ctx.moveTo(0, -1.5);
  ctx.lineTo(180 * breathe, -1.5);
  ctx.lineTo(180 * breathe, 1.5);
  ctx.lineTo(0, 1.5);
  ctx.closePath();
  ctx.fillStyle = scanGrad;
  ctx.fill();
  ctx.restore();

  // ── Bright core pupil ────────────────────────────────────
  const coreIntensity = 0.5 + Math.sin(t * 0.001) * 0.18;
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, 22 * breathe);
  core.addColorStop(0, `rgba(255,230,210,${coreIntensity})`);
  core.addColorStop(0.25, `rgba(255,40,20,${coreIntensity * 0.7})`);
  core.addColorStop(0.6, `rgba(160,0,0,${coreIntensity * 0.3})`);
  core.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath();
  ctx.arc(cx, cy, 22 * breathe, 0, Math.PI * 2);
  ctx.fillStyle = core;
  ctx.fill();

  // ── Pupil ring bright flash ───────────────────────────────
  ctx.beginPath();
  ctx.arc(cx, cy, 18 * breathe, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(255,100,80,${0.15 + Math.sin(t * 0.001) * 0.1})`;
  ctx.lineWidth = 2;
  ctx.stroke();
}

// ─────────────────────────────────────────────────────────────
//  TRON — The Grid with live light-cycle data streams
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

function drawTron(
  ctx: CanvasRenderingContext2D, w: number, h: number, t: number,
  state: CanvasState, sw: number
) {
  ctx.clearRect(0, 0, w, h);

  const G = 48;
  const sidebarW = sw;
  const cyan = (a: number) => `rgba(0,240,255,${a})`;
  const white = (a: number) => `rgba(200,255,255,${a})`;

  // ── Grid ──────────────────────────────────────────────────
  ctx.lineWidth = 0.5;
  for (let x = sidebarW; x <= w; x += G) {
    ctx.beginPath();
    ctx.moveTo(x, 0); ctx.lineTo(x, h);
    ctx.strokeStyle = cyan(0.055 + Math.sin(t * 0.001 + x * 0.008) * 0.015);
    ctx.stroke();
  }
  for (let y = 0; y <= h; y += G) {
    ctx.beginPath();
    ctx.moveTo(sidebarW, y); ctx.lineTo(w, y);
    ctx.strokeStyle = cyan(0.055 + Math.sin(t * 0.001 + y * 0.008) * 0.015);
    ctx.stroke();
  }

  // ── Grid intersection flares ─────────────────────────────
  for (let x = sidebarW; x <= w; x += G) {
    for (let y = 0; y <= h; y += G) {
      const pulse = Math.sin(t * 0.0025 + x * 0.05 + y * 0.05);
      if (pulse > 0.72) {
        const a = (pulse - 0.72) * 1.0;
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fillStyle = cyan(a);
        ctx.fill();
      }
    }
  }

  // ── Spawn new light streams ───────────────────────────────
  if (t - state.lastStreamSpawn > 350 && state.streams.length < 16) {
    state.streams.push(spawnStream(w, h, sidebarW));
    state.lastStreamSpawn = t;
  }

  // ── Draw light streams ────────────────────────────────────
  state.streams = state.streams.filter(s => s.age < s.maxAge);
  state.streams.forEach(s => {
    s.age += 16;
    const fade = Math.sin((s.age / s.maxAge) * Math.PI);
    const pos = (s.dir === "h" ? s.x : s.y) + s.speed * (s.age / 16) * 0.8;
    const tail = pos - s.len * Math.sign(s.speed);

    ctx.shadowBlur = 12;
    ctx.shadowColor = cyan(0.9);
    ctx.lineWidth = 2;

    if (s.dir === "h") {
      const g = ctx.createLinearGradient(tail, 0, pos, 0);
      g.addColorStop(0, cyan(0));
      g.addColorStop(0.7, cyan(0.25 * fade * s.opacity));
      g.addColorStop(1, white(0.95 * fade * s.opacity));
      ctx.beginPath(); ctx.moveTo(tail, s.y); ctx.lineTo(pos, s.y);
      ctx.strokeStyle = g; ctx.stroke();
      // Head flare
      ctx.beginPath(); ctx.arc(pos, s.y, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = white(fade * s.opacity); ctx.fill();
      // Side wings
      ctx.lineWidth = 1;
      ctx.strokeStyle = cyan(0.2 * fade * s.opacity);
      ctx.beginPath(); ctx.moveTo(pos, s.y - G * 0.4); ctx.lineTo(pos, s.y - 2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pos, s.y + 2); ctx.lineTo(pos, s.y + G * 0.4); ctx.stroke();
    } else {
      const g = ctx.createLinearGradient(0, tail, 0, pos);
      g.addColorStop(0, cyan(0));
      g.addColorStop(0.7, cyan(0.25 * fade * s.opacity));
      g.addColorStop(1, white(0.95 * fade * s.opacity));
      ctx.beginPath(); ctx.moveTo(s.x, tail); ctx.lineTo(s.x, pos);
      ctx.strokeStyle = g; ctx.stroke();
      ctx.beginPath(); ctx.arc(s.x, pos, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = white(fade * s.opacity); ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = cyan(0.2 * fade * s.opacity);
      ctx.beginPath(); ctx.moveTo(s.x - G * 0.4, pos); ctx.lineTo(s.x - 2, pos); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(s.x + 2, pos); ctx.lineTo(s.x + G * 0.4, pos); ctx.stroke();
    }
    ctx.shadowBlur = 0;
  });

  // ── Sidebar edge circuit trace ────────────────────────────
  const traceY = (t * 0.08) % h;
  const traceH = 120;
  const traceGrad = ctx.createLinearGradient(0, traceY - traceH, 0, traceY + traceH);
  traceGrad.addColorStop(0, cyan(0));
  traceGrad.addColorStop(0.5, cyan(0.7));
  traceGrad.addColorStop(1, cyan(0));
  ctx.lineWidth = 1.5;
  ctx.shadowBlur = 8;
  ctx.shadowColor = cyan(1);
  ctx.beginPath();
  ctx.moveTo(sidebarW, traceY - traceH);
  ctx.lineTo(sidebarW, traceY + traceH);
  ctx.strokeStyle = traceGrad;
  ctx.stroke();
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

  // ── VK iris — centered in the chat content area ───────────
  const ix = sw + chatW * 0.5;
  const iy = h * 0.40;
  const iR = Math.min(chatW * 0.32, 240);
  const iBreath = 0.95 + Math.sin(t * 0.0009) * 0.05;
  const iSpin = t * 0.00018;

  // Outer glow
  const outerGlow = ctx.createRadialGradient(ix, iy, iR * 0.5, ix, iy, iR * 1.8);
  outerGlow.addColorStop(0, amber(0.08));
  outerGlow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.beginPath();
  ctx.arc(ix, iy, iR * 1.8, 0, Math.PI * 2);
  ctx.fillStyle = outerGlow;
  ctx.fill();

  // Concentric measurement rings (like an ophthalmoscope)
  [1.0, 0.82, 0.65, 0.50, 0.36, 0.24, 0.14].forEach((scale, i) => {
    ctx.beginPath();
    ctx.arc(ix, iy, iR * scale * iBreath, 0, Math.PI * 2);
    const a = 0.12 + i * 0.08 + Math.sin(t * 0.001 + i * 0.5) * 0.03;
    ctx.strokeStyle = amber(a);
    ctx.lineWidth = i === 0 ? 1.5 : 0.75;
    ctx.stroke();
    // Tick marks on outer ring
    if (i === 0) {
      for (let tick = 0; tick < 36; tick++) {
        const ang = (tick / 36) * Math.PI * 2;
        const r1 = iR * 0.96;
        const r2 = iR * 1.0;
        ctx.beginPath();
        ctx.moveTo(ix + Math.cos(ang) * r1, iy + Math.sin(ang) * r1);
        ctx.lineTo(ix + Math.cos(ang) * r2, iy + Math.sin(ang) * r2);
        ctx.strokeStyle = amber(0.4);
        ctx.lineWidth = tick % 9 === 0 ? 1.5 : 0.5;
        ctx.stroke();
      }
    }
  });

  // Iris petals (slow rotation)
  const petalCount = 14;
  for (let i = 0; i < petalCount; i++) {
    const ang = iSpin + (i / petalCount) * Math.PI * 2;
    const r1 = iR * 0.18 * iBreath;
    const r2 = iR * 0.52 * iBreath;
    const spread = 0.18;
    const brightness = 0.10 + Math.sin(t * 0.0018 + i * 0.9) * 0.05;
    ctx.beginPath();
    ctx.moveTo(ix + Math.cos(ang - spread) * r1, iy + Math.sin(ang - spread) * r1);
    ctx.lineTo(ix + Math.cos(ang) * r2, iy + Math.sin(ang) * r2);
    ctx.lineTo(ix + Math.cos(ang + spread) * r1, iy + Math.sin(ang + spread) * r1);
    ctx.closePath();
    ctx.fillStyle = amber(brightness);
    ctx.fill();
  }

  // Scan reticle (cross-hairs rotating around iris)
  const reticleAngle = t * 0.0004;
  const rx1 = ix + Math.cos(reticleAngle) * iR * 0.72;
  const ry1 = iy + Math.sin(reticleAngle) * iR * 0.72;
  const rx2 = ix + Math.cos(reticleAngle + Math.PI) * iR * 0.72;
  const ry2 = iy + Math.sin(reticleAngle + Math.PI) * iR * 0.72;
  ctx.beginPath();
  ctx.moveTo(rx1, ry1); ctx.lineTo(rx2, ry2);
  ctx.strokeStyle = amber(0.35);
  ctx.lineWidth = 0.75;
  ctx.stroke();
  // Reticle bracket at head
  const bSize = 7;
  [[rx1, ry1], [rx2, ry2]].forEach(([bx, by]) => {
    const perp = reticleAngle + Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(bx + Math.cos(perp) * bSize, by + Math.sin(perp) * bSize);
    ctx.lineTo(bx, by);
    ctx.lineTo(bx - Math.cos(perp) * bSize, by - Math.sin(perp) * bSize);
    ctx.strokeStyle = amber(0.6);
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  // Pupil (deep black center, faint glow)
  ctx.beginPath();
  ctx.arc(ix, iy, iR * 0.12 * iBreath, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(0,0,0,0.9)";
  ctx.fill();
  ctx.strokeStyle = amber(0.5);
  ctx.lineWidth = 1;
  ctx.stroke();

  // ── Phosphor readout: oscilloscope above input bar ────────
  const oscX = sw + 20;
  const oscW = chatW * 0.55;
  const oscY = h - 108; // 108px from bottom keeps it above the message input
  const oscH = 36;
  const points = 80;

  // Oscilloscope background panel
  ctx.fillStyle = "rgba(20,10,0,0.35)";
  ctx.fillRect(oscX, oscY - oscH - 4, oscW, oscH + 8);
  ctx.strokeStyle = amber(0.22);
  ctx.lineWidth = 1;
  ctx.strokeRect(oscX, oscY - oscH - 4, oscW, oscH + 8);

  // Oscilloscope label
  ctx.font = "9px 'JetBrains Mono', monospace";
  ctx.fillStyle = amber(0.45);
  ctx.fillText("EMOTIONAL RESPONSE / VK-VI", oscX + 4, oscY - oscH + 0);

  // Waveform
  ctx.beginPath();
  for (let i = 0; i <= points; i++) {
    const px = oscX + (i / points) * oscW;
    const wave =
      Math.sin(i * 0.18 + t * 0.003) * 0.4 +
      Math.sin(i * 0.42 + t * 0.002) * 0.25 +
      Math.sin(i * 0.09 + t * 0.004) * 0.2 +
      Math.sin(i * 0.7 + t * 0.006) * 0.08;
    const py = oscY - oscH * 0.5 - wave * oscH * 0.38;
    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
  }
  ctx.strokeStyle = amber(0.65);
  ctx.lineWidth = 1.2;
  ctx.shadowBlur = 6;
  ctx.shadowColor = amber(0.8);
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Scan cursor
  const cursorX = oscX + ((t * 0.04) % oscW);
  ctx.beginPath();
  ctx.moveTo(cursorX, oscY - oscH - 4);
  ctx.lineTo(cursorX, oscY + 4);
  ctx.strokeStyle = amber(0.35);
  ctx.lineWidth = 1;
  ctx.stroke();

  // ── Ambient city glow at bottom ──────────────────────────
  const horizon = ctx.createLinearGradient(sw, h * 0.7, sw, h);
  horizon.addColorStop(0, "rgba(0,0,0,0)");
  horizon.addColorStop(0.5, dimAmber(0.06));
  horizon.addColorStop(1, dimAmber(0.14));
  ctx.fillStyle = horizon;
  ctx.fillRect(sw, h * 0.7, chatW, h * 0.3);
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

function drawShadowrun(
  ctx: CanvasRenderingContext2D, w: number, h: number, t: number,
  state: CanvasState, sw: number
) {
  ctx.clearRect(0, 0, w, h);

  const sidebarW = sw;
  const teal = (a: number) => `rgba(0,221,192,${a})`;
  const purple = (a: number) => `rgba(180,60,255,${a})`;

  // ── Matrix glyph rain ────────────────────────────────────
  if (state.glyphs.length < 40) initShadowrunGlyphs(w, h, sw, state);
  const colW = 14;

  state.glyphs.forEach(g => {
    // Occasionally flip glyph
    if (Math.random() < 0.002) {
      g.char = SR_GLYPHS[Math.floor(Math.random() * SR_GLYPHS.length)];
    }
    g.y += g.speed;
    if (g.y > h + 20) {
      g.y = -20;
      g.col = Math.floor(Math.random() * Math.floor(w / colW));
      g.speed = Math.random() * 1.8 + 0.8;
      g.bright = Math.random() < 0.08;
    }

    const x = g.col * colW;
    if (x < sidebarW) return; // don't draw over sidebar

    // Faint trail above
    ctx.font = `${colW - 2}px monospace`;
    ctx.fillStyle = teal(g.bright ? g.opacity * 0.3 : g.opacity * 0.12);
    ctx.fillText(g.char, x, g.y - colW);
    ctx.fillStyle = teal(g.bright ? g.opacity * 0.6 : g.opacity * 0.2);
    ctx.fillText(g.char, x, g.y);
    // Bright head
    if (g.bright) {
      ctx.fillStyle = "rgba(200,255,250,0.9)";
    } else {
      ctx.fillStyle = g.col % 7 === 0 ? purple(g.opacity * 0.55) : teal(g.opacity * 0.42);
    }
    ctx.fillText(g.char, x, g.y + colW * 0.5);
  });

  // ── Awakened rune circles ─────────────────────────────────
  if (t - state.lastRuneSpawn > 4000 && state.runes.length < 4) {
    state.lastRuneSpawn = t;
    const margin = 120;
    state.runes.push({
      x: sidebarW + margin + Math.random() * (w - sidebarW - margin * 2),
      y: margin + Math.random() * (h - margin * 2),
      r: 60 + Math.random() * 50,
      age: 0,
      maxAge: 6000 + Math.random() * 4000,
      spin: (Math.random() - 0.5) * 0.0003,
    });
  }

  state.runes = state.runes.filter(r => r.age < r.maxAge);
  state.runes.forEach(rune => {
    rune.age += 16;
    const progress = rune.age / rune.maxAge;
    const fade = Math.sin(progress * Math.PI);

    ctx.save();
    ctx.translate(rune.x, rune.y);
    ctx.rotate(rune.spin * rune.age);

    // Outer circle
    ctx.beginPath();
    ctx.arc(0, 0, rune.r, 0, Math.PI * 2);
    ctx.strokeStyle = purple(0.25 * fade);
    ctx.lineWidth = 1;
    ctx.stroke();

    // Inner circle
    ctx.beginPath();
    ctx.arc(0, 0, rune.r * 0.7, 0, Math.PI * 2);
    ctx.strokeStyle = teal(0.18 * fade);
    ctx.lineWidth = 0.75;
    ctx.stroke();

    // Rune characters around outer circle
    const numChars = 8;
    ctx.font = `${Math.floor(rune.r * 0.22)}px serif`;
    for (let i = 0; i < numChars; i++) {
      const ang = (i / numChars) * Math.PI * 2 - Math.PI / 2;
      const cx = Math.cos(ang) * rune.r * 0.85;
      const cy = Math.sin(ang) * rune.r * 0.85;
      const char = SR_RUNE_CHARS[Math.floor((rune.age * 0.001 + i * 3) % SR_RUNE_CHARS.length)];
      ctx.fillStyle = teal(0.35 * fade);
      ctx.fillText(char, cx - 5, cy + 5);
    }

    // Crosshair lines
    ctx.lineWidth = 0.5;
    ctx.strokeStyle = purple(0.18 * fade);
    [[0, -rune.r, 0, rune.r], [-rune.r, 0, rune.r, 0]].forEach(([x1, y1, x2, y2]) => {
      ctx.beginPath();
      ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
      ctx.stroke();
    });

    ctx.restore();
  });

  // ── AR bracket overlays on sidebar ──────────────────────
  const bracketOpacity = 0.12 + Math.sin(t * 0.002) * 0.04;
  const bx = 8; const bw = sidebarW - 16;
  const by = h * 0.18; const bh = h * 0.56;
  const bs = 16; // bracket size
  ctx.lineWidth = 1;
  ctx.strokeStyle = teal(bracketOpacity);
  // Top-left bracket
  ctx.beginPath(); ctx.moveTo(bx + bs, by); ctx.lineTo(bx, by); ctx.lineTo(bx, by + bs); ctx.stroke();
  // Top-right bracket
  ctx.beginPath(); ctx.moveTo(bx + bw - bs, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + bs); ctx.stroke();
  // Bottom-left bracket
  ctx.beginPath(); ctx.moveTo(bx + bs, by + bh); ctx.lineTo(bx, by + bh); ctx.lineTo(bx, by + bh - bs); ctx.stroke();
  // Bottom-right bracket
  ctx.beginPath(); ctx.moveTo(bx + bw - bs, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - bs); ctx.stroke();

  // ── Sidebar right-edge neon line ─────────────────────────
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
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = edgeGrad;
  ctx.shadowBlur = 10;
  ctx.shadowColor = teal(1);
  ctx.beginPath();
  ctx.moveTo(sidebarW, 0); ctx.lineTo(sidebarW, h);
  ctx.stroke();
  ctx.shadowBlur = 0;
}

// ─────────────────────────────────────────────────────────────
//  Component
// ─────────────────────────────────────────────────────────────
const CANVAS_THEMES = new Set(["hal9000", "tron", "bladerunner", "shadowrun"]);

export function ThemeAmbientCanvas() {
  const theme        = useSettingsStore(s => s.theme);
  const sidebarOpen  = useSettingsStore(s => s.sidebarOpen);
  const sidebarSlim  = useSettingsStore(s => s.sidebarSlim);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef    = useRef<number>(0);
  const stateRef  = useRef<CanvasState>(mkState());
  // Live sidebar width — read on every frame so animations snap when sidebar toggles
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
      if (theme === "shadowrun") {
        initShadowrunGlyphs(canvas.width, canvas.height, swRef.current, stateRef.current);
      }
    };
    resize();
    window.addEventListener("resize", resize);

    let running = true;
    const loop = (ts: number) => {
      if (!running) return;
      const w  = canvas.width;
      const h  = canvas.height;
      const sw = swRef.current;
      const state = stateRef.current;

      switch (theme) {
        case "hal9000":     drawHAL(ctx, w, h, ts, sw); break;
        case "tron":        drawTron(ctx, w, h, ts, state, sw); break;
        case "bladerunner": drawBladeRunner(ctx, w, h, ts, sw); break;
        case "shadowrun":   drawShadowrun(ctx, w, h, ts, state, sw); break;
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
        opacity: 1,
      }}
      aria-hidden="true"
    />
  );
}
