"use client";

import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";

/**
 * Pure CSS/SVG architectural backdrop that renders palace structure
 * based on the current navigation level (lobby/wing/room).
 * Replaces particle effects with structural elements that reinforce
 * the Memory Palace spatial metaphor.
 */
export function PalaceArchitecture() {
  const level = usePalaceStore((s) => s.location.level);
  const colors = usePalaceColors();

  const lineColor = colors.accent;
  const lineOpacity = colors.isLight ? 0.1 : 0.14;
  const fillOpacity = colors.isLight ? 0.04 : 0.06;

  return (
    <div
      className="absolute inset-0 overflow-hidden pointer-events-none"
      style={{ zIndex: 0 }}
    >
      <svg
        viewBox="0 0 1200 800"
        preserveAspectRatio="xMidYMid slice"
        className="w-full h-full"
        style={{
          animation: "palaceArchFadeIn 1.2s ease-out both",
        }}
      >
        <defs>
          {/* Vertical fade — lines disappear toward the bottom */}
          <linearGradient id="archFadeDown" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity={lineOpacity} />
            <stop offset="85%" stopColor={lineColor} stopOpacity={lineOpacity * 0.4} />
            <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
          </linearGradient>
          {/* Horizontal fade for floor lines */}
          <linearGradient id="archFadeCenter" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={lineColor} stopOpacity={0} />
            <stop offset="30%" stopColor={lineColor} stopOpacity={lineOpacity * 0.6} />
            <stop offset="50%" stopColor={lineColor} stopOpacity={lineOpacity} />
            <stop offset="70%" stopColor={lineColor} stopOpacity={lineOpacity * 0.6} />
            <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
          </linearGradient>
          {/* Radial glow for vanishing point */}
          <radialGradient id="archVanishGlow" cx="50%" cy="42%" r="30%">
            <stop offset="0%" stopColor={lineColor} stopOpacity={fillOpacity * 1.5} />
            <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
          </radialGradient>
          {/* Subtle fill for arch interiors */}
          <linearGradient id="archFillUp" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor={lineColor} stopOpacity={0} />
            <stop offset="100%" stopColor={lineColor} stopOpacity={fillOpacity} />
          </linearGradient>
        </defs>

        {level === "lobby" && (
          <LobbyStructure color={lineColor} lo={lineOpacity} fo={fillOpacity} />
        )}
        {level === "wing" && (
          <CorridorStructure color={lineColor} lo={lineOpacity} fo={fillOpacity} />
        )}
        {(level === "hall" || level === "room") && (
          <ChamberStructure color={lineColor} lo={lineOpacity} fo={fillOpacity} />
        )}
      </svg>
    </div>
  );
}

/* ── Lobby: Grand Atrium ──────────────────────────────────────────── */
/* A grand vaulted space with columns, a dome arch, and perspective
   floor lines converging to a vanishing point. Suggests a vast,
   open hall with multiple passages leading deeper. */
function LobbyStructure({
  color,
  lo,
  fo,
}: {
  color: string;
  lo: number;
  fo: number;
}) {
  return (
    <g>
      {/* Vanishing point glow */}
      <rect x="0" y="0" width="1200" height="800" fill="url(#archVanishGlow)" />

      {/* ── Grand arch — primary dome ── */}
      <path
        d="M 160,580 Q 160,80 600,60 Q 1040,80 1040,580"
        fill="url(#archFillUp)"
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity={lo}
      />
      {/* Inner arch — smaller, concentric */}
      <path
        d="M 260,580 Q 260,160 600,140 Q 940,160 940,580"
        fill="none"
        stroke={color}
        strokeWidth="1"
        strokeOpacity={lo * 0.6}
      />
      {/* Keystone accent at apex */}
      <path
        d="M 585,62 L 600,48 L 615,62"
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity={lo * 0.8}
      />

      {/* ── Columns — left side ── */}
      <Column x={168} y1={180} y2={580} w={14} color={color} opacity={lo} />
      <Column x={268} y1={220} y2={580} w={12} color={color} opacity={lo * 0.7} />

      {/* ── Columns — right side ── */}
      <Column x={1018} y1={180} y2={580} w={14} color={color} opacity={lo} />
      <Column x={920} y1={220} y2={580} w={12} color={color} opacity={lo * 0.7} />

      {/* ── Column capitals (decorative tops) ── */}
      <rect x={158} y={176} width={34} height={6} rx={1}
        fill={color} fillOpacity={fo} stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.5} />
      <rect x={1008} y={176} width={34} height={6} rx={1}
        fill={color} fillOpacity={fo} stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.5} />

      {/* ── Floor line ── */}
      <line x1="100" y1="580" x2="1100" y2="580"
        stroke="url(#archFadeCenter)" strokeWidth="1" />

      {/* ── Perspective floor grid ── */}
      {/* Radiating lines from vanishing point */}
      {[-400, -250, -120, 0, 120, 250, 400].map((offset, i) => (
        <line
          key={`floor-${i}`}
          x1="600" y1="420"
          x2={600 + offset * 1.4} y2="800"
          stroke={color}
          strokeWidth="0.5"
          strokeOpacity={lo * (0.4 - Math.abs(offset) * 0.0005)}
        />
      ))}

      {/* Horizontal depth lines (perspective cross-bars) */}
      {[480, 530, 560].map((y, i) => {
        const narrowFactor = 1 - (580 - y) / 400;
        const halfW = 200 + narrowFactor * 300;
        return (
          <line
            key={`hline-${i}`}
            x1={600 - halfW} y1={y}
            x2={600 + halfW} y2={y}
            stroke={color}
            strokeWidth="0.5"
            strokeOpacity={lo * (0.2 + i * 0.08)}
          />
        );
      })}

      {/* ── Decorative motifs — small arches between columns (arcade) ── */}
      {/* Left arcade */}
      <path d="M 168,320 Q 218,290 268,320" fill="none"
        stroke={color} strokeWidth="0.8" strokeOpacity={lo * 0.4} />
      <path d="M 168,400 Q 218,370 268,400" fill="none"
        stroke={color} strokeWidth="0.8" strokeOpacity={lo * 0.35} />

      {/* Right arcade */}
      <path d="M 920,320 Q 969,290 1018,320" fill="none"
        stroke={color} strokeWidth="0.8" strokeOpacity={lo * 0.4} />
      <path d="M 920,400 Q 969,370 1018,400" fill="none"
        stroke={color} strokeWidth="0.8" strokeOpacity={lo * 0.35} />

      {/* ── Floor rosette (central ornament) ── */}
      <circle cx="600" cy="620" r="40"
        fill="none" stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.25} />
      <circle cx="600" cy="620" r="20"
        fill="none" stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.2} />
      <circle cx="600" cy="620" r="3"
        fill={color} fillOpacity={fo * 0.8} />
    </g>
  );
}

/* ── Wing: Corridor ───────────────────────────────────────────────── */
/* A receding corridor with repeating arches, walls, and a center-line
   floor. Creates the sense of walking through a gallery passage. */
function CorridorStructure({
  color,
  lo,
  fo,
}: {
  color: string;
  lo: number;
  fo: number;
}) {
  /* Generate 4 arches receding into depth */
  const arches = [
    { left: 140, right: 1060, top: 100, opacity: 1 },
    { left: 260, right: 940, top: 170, opacity: 0.7 },
    { left: 360, right: 840, top: 230, opacity: 0.45 },
    { left: 440, right: 760, top: 280, opacity: 0.25 },
  ];

  return (
    <g>
      {/* Vanishing point glow — deeper in corridor */}
      <rect x="0" y="0" width="1200" height="800" fill="url(#archVanishGlow)" />

      {/* ── Receding arches (tunnel effect) ── */}
      {arches.map((a, i) => {
        const midX = (a.left + a.right) / 2;
        return (
          <g key={`arch-${i}`}>
            {/* Arch curve */}
            <path
              d={`M ${a.left},580 Q ${a.left},${a.top} ${midX},${a.top - 20} Q ${a.right},${a.top} ${a.right},580`}
              fill={i === 0 ? "url(#archFillUp)" : "none"}
              stroke={color}
              strokeWidth={1.5 - i * 0.3}
              strokeOpacity={lo * a.opacity}
            />

            {/* Vertical columns on each side */}
            <line x1={a.left} y1={a.top + 40} x2={a.left} y2={580}
              stroke={color} strokeWidth={1.2 - i * 0.25} strokeOpacity={lo * a.opacity} />
            <line x1={a.right} y1={a.top + 40} x2={a.right} y2={580}
              stroke={color} strokeWidth={1.2 - i * 0.25} strokeOpacity={lo * a.opacity} />

            {/* Column base marks */}
            {i < 3 && (
              <>
                <rect x={a.left - 6} y={574} width={12} height={6} rx={1}
                  fill={color} fillOpacity={fo * a.opacity} />
                <rect x={a.right - 6} y={574} width={12} height={6} rx={1}
                  fill={color} fillOpacity={fo * a.opacity} />
              </>
            )}
          </g>
        );
      })}

      {/* ── Floor line ── */}
      <line x1="80" y1="580" x2="1120" y2="580"
        stroke="url(#archFadeCenter)" strokeWidth="1" />

      {/* ── Center floor guide line ── */}
      <line x1="600" y1="580" x2="600" y2="780"
        stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.3} />

      {/* ── Floor perspective lines ── */}
      {arches.map((a, i) => (
        <g key={`fline-${i}`}>
          <line x1={a.left} y1={580} x2={600 + (a.left - 600) * 2.2} y2={800}
            stroke={color} strokeWidth="0.4" strokeOpacity={lo * 0.2 * a.opacity} />
          <line x1={a.right} y1={580} x2={600 + (a.right - 600) * 2.2} y2={800}
            stroke={color} strokeWidth="0.4" strokeOpacity={lo * 0.2 * a.opacity} />
        </g>
      ))}

      {/* ── Cross-beams between arch pairs ── */}
      {arches.slice(0, 3).map((a, i) => {
        const next = arches[i + 1];
        const beamY = (a.top + next.top) / 2 + 30;
        return (
          <g key={`beam-${i}`}>
            <line x1={a.left} y1={beamY} x2={next.left} y2={beamY}
              stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.2 * a.opacity} />
            <line x1={a.right} y1={beamY} x2={next.right} y2={beamY}
              stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.2 * a.opacity} />
          </g>
        );
      })}

      {/* ── Wall panels (left side) — suggesting doors ── */}
      {[0, 1].map((i) => {
        const a = arches[i];
        const next = arches[i + 1];
        const midY = (a.top + 120 + 580) / 2;
        const midLeft = (a.left + next.left) / 2;
        const panelW = (next.left - a.left) * 0.5;
        const panelH = 120;
        return (
          <rect
            key={`lpanel-${i}`}
            x={midLeft - panelW / 2}
            y={midY - panelH / 2}
            width={panelW}
            height={panelH}
            rx={3}
            fill={color}
            fillOpacity={fo * 0.4 * a.opacity}
            stroke={color}
            strokeWidth="0.5"
            strokeOpacity={lo * 0.25 * a.opacity}
          />
        );
      })}

      {/* ── Wall panels (right side) ── */}
      {[0, 1].map((i) => {
        const a = arches[i];
        const next = arches[i + 1];
        const midY = (a.top + 120 + 580) / 2;
        const midRight = (a.right + next.right) / 2;
        const panelW = (a.right - next.right) * 0.5;
        const panelH = 120;
        return (
          <rect
            key={`rpanel-${i}`}
            x={midRight - panelW / 2}
            y={midY - panelH / 2}
            width={panelW}
            height={panelH}
            rx={3}
            fill={color}
            fillOpacity={fo * 0.4 * a.opacity}
            stroke={color}
            strokeWidth="0.5"
            strokeOpacity={lo * 0.25 * a.opacity}
          />
        );
      })}
    </g>
  );
}

/* ── Room: Chamber ────────────────────────────────────────────────── */
/* An enclosed chamber with shelf/drawer grid on the walls and a
   vaulted ceiling. Suggests a room full of organized storage. */
function ChamberStructure({
  color,
  lo,
  fo,
}: {
  color: string;
  lo: number;
  fo: number;
}) {
  const shelfCols = 5;
  const shelfRows = 3;

  return (
    <g>
      {/* Vanishing point glow — centered in chamber */}
      <rect x="0" y="0" width="1200" height="800" fill="url(#archVanishGlow)" />

      {/* ── Vaulted ceiling arch ── */}
      <path
        d="M 120,560 Q 120,60 600,40 Q 1080,60 1080,560"
        fill="url(#archFillUp)"
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity={lo}
      />

      {/* Inner ceiling detail */}
      <path
        d="M 200,560 Q 200,120 600,100 Q 1000,120 1000,560"
        fill="none"
        stroke={color}
        strokeWidth="0.8"
        strokeOpacity={lo * 0.4}
      />

      {/* ── Wall outlines ── */}
      <line x1="120" y1="140" x2="120" y2="560"
        stroke={color} strokeWidth="1.2" strokeOpacity={lo * 0.8} />
      <line x1="1080" y1="140" x2="1080" y2="560"
        stroke={color} strokeWidth="1.2" strokeOpacity={lo * 0.8} />

      {/* ── Floor line ── */}
      <line x1="80" y1="560" x2="1120" y2="560"
        stroke="url(#archFadeCenter)" strokeWidth="1" />

      {/* ── Left wall: drawer grid ── */}
      <DrawerWallGrid
        x={130} y={210} width={140} height={310}
        cols={shelfCols} rows={shelfRows}
        color={color} lo={lo} fo={fo}
      />

      {/* ── Right wall: drawer grid ── */}
      <DrawerWallGrid
        x={930} y={210} width={140} height={310}
        cols={shelfCols} rows={shelfRows}
        color={color} lo={lo} fo={fo}
      />

      {/* ── Back wall: larger drawer grid (perspective) ── */}
      <DrawerWallGrid
        x={340} y={180} width={520} height={340}
        cols={7} rows={shelfRows}
        color={color} lo={lo * 0.5} fo={fo * 0.6}
      />

      {/* ── Pilasters (flat column details) on walls ── */}
      <Column x={124} y1={140} y2={560} w={8} color={color} opacity={lo * 0.6} />
      <Column x={268} y1={200} y2={560} w={6} color={color} opacity={lo * 0.35} />
      <Column x={1068} y1={140} y2={560} w={8} color={color} opacity={lo * 0.6} />
      <Column x={926} y1={200} y2={560} w={6} color={color} opacity={lo * 0.35} />

      {/* ── Central pedestal ── */}
      <ellipse cx="600" cy="580" rx="60" ry="8"
        fill={color} fillOpacity={fo * 0.5}
        stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.3} />
      <rect x="585" y="530" width="30" height="50" rx={2}
        fill={color} fillOpacity={fo * 0.3}
        stroke={color} strokeWidth="0.5" strokeOpacity={lo * 0.25} />

      {/* ── Ceiling ribs (radial) ── */}
      {[-30, -15, 0, 15, 30].map((angle, i) => {
        const rad = (angle * Math.PI) / 180;
        const startX = 600 + Math.sin(rad) * 20;
        const startY = 55 + Math.abs(angle) * 0.8;
        const endX = 600 + Math.sin(rad) * 480;
        const endY = 560;
        return (
          <line
            key={`rib-${i}`}
            x1={startX} y1={startY}
            x2={endX} y2={endY}
            stroke={color}
            strokeWidth="0.4"
            strokeOpacity={lo * 0.2}
          />
        );
      })}
    </g>
  );
}

/* ── Reusable sub-components ──────────────────────────────────────── */

/** A single architectural column with base and capital. */
function Column({
  x,
  y1,
  y2,
  w,
  color,
  opacity,
}: {
  x: number;
  y1: number;
  y2: number;
  w: number;
  color: string;
  opacity: number;
}) {
  return (
    <g>
      {/* Shaft */}
      <rect
        x={x - w / 2}
        y={y1}
        width={w}
        height={y2 - y1}
        fill={color}
        fillOpacity={opacity * 0.3}
        stroke={color}
        strokeWidth="0.5"
        strokeOpacity={opacity * 0.6}
      />
      {/* Capital (top) */}
      <rect
        x={x - w * 0.8}
        y={y1 - 3}
        width={w * 1.6}
        height={4}
        rx={1}
        fill={color}
        fillOpacity={opacity * 0.4}
      />
      {/* Base (bottom) */}
      <rect
        x={x - w * 0.7}
        y={y2 - 2}
        width={w * 1.4}
        height={4}
        rx={1}
        fill={color}
        fillOpacity={opacity * 0.35}
      />
    </g>
  );
}

/** A grid of rectangles suggesting drawer slots on a wall. */
function DrawerWallGrid({
  x,
  y,
  width,
  height,
  cols,
  rows,
  color,
  lo,
  fo,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  cols: number;
  rows: number;
  color: string;
  lo: number;
  fo: number;
}) {
  const gap = 4;
  const cellW = (width - gap * (cols + 1)) / cols;
  const cellH = (height - gap * (rows + 1)) / rows;

  const cells = [];
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const cx = x + gap + col * (cellW + gap);
      const cy = y + gap + row * (cellH + gap);
      cells.push(
        <rect
          key={`${row}-${col}`}
          x={cx}
          y={cy}
          width={cellW}
          height={cellH}
          rx={2}
          fill={color}
          fillOpacity={fo * 0.3}
          stroke={color}
          strokeWidth="0.5"
          strokeOpacity={lo * 0.35}
        />,
      );
    }
  }

  return (
    <g>
      {/* Shelf frame */}
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        rx={3}
        fill="none"
        stroke={color}
        strokeWidth="0.8"
        strokeOpacity={lo * 0.5}
      />
      {/* Individual drawer slots */}
      {cells}
    </g>
  );
}
