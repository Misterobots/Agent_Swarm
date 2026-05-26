"use client";

import { useEffect, useRef } from "react";
import { useSettingsStore } from "@/lib/stores/settings-store";

const SW_FULL = 256;

const READOUTS = [
  { label: "MEM",  seedA: 0.0013, seedB: 0.0 },
  { label: "COM",  seedA: 0.0009, seedB: 2.1 },
  { label: "SNS",  seedA: 0.0017, seedB: 4.4 },
  { label: "PWR",  seedA: 0.0011, seedB: 1.3 },
];

// Renders only for LCARS themes — adds structural chrome:
//  • 6 px left accent strip (the vertical "elbow arm")
//  • 4 animated LCARS readout bars near the bottom of the sidebar
export function ThemeLCARSDecor() {
  const theme       = useSettingsStore(s => s.theme);
  const sidebarOpen = useSettingsStore(s => s.sidebarOpen);
  const sidebarSlim = useSettingsStore(s => s.sidebarSlim);

  const barsRef   = useRef<(HTMLDivElement | null)[]>([]);
  const rafRef    = useRef<number>(0);

  const isLCARS = theme.startsWith("lcars");
  const visible = isLCARS && sidebarOpen && !sidebarSlim;

  useEffect(() => {
    if (!visible) return;

    let running = true;
    const loop = (ts: number) => {
      if (!running) return;
      READOUTS.forEach((r, i) => {
        const bar = barsRef.current[i];
        if (!bar) return;
        const level = 0.28 + Math.abs(Math.sin(ts * r.seedA + r.seedB)) * 0.58;
        bar.style.width = `${Math.round(level * 100)}%`;
        // subtle opacity beat
        const beat = 0.62 + Math.sin(ts * 0.0006 + r.seedB) * 0.28;
        bar.style.opacity = String(beat.toFixed(2));
      });
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => { running = false; cancelAnimationFrame(rafRef.current); };
  }, [visible]);

  if (!visible) return null;

  return (
    <>
      {/* Vertical elbow arm — 6 px left strip, full sidebar height */}
      <div
        aria-hidden="true"
        style={{
          position:      "fixed",
          top:            0,
          left:           0,
          width:          6,
          height:         "100dvh",
          pointerEvents: "none",
          zIndex:         10,
          background:    "linear-gradient(to bottom, var(--lcars-elbow-a) 0%, var(--lcars-elbow-b) 28%, var(--lcars-elbow-c) 60%, var(--lcars-elbow-d) 88%, var(--lcars-elbow-a))",
          opacity:        0.92,
        }}
      />

      {/* LCARS data readout panel — sits above the sidebar footer */}
      <div
        aria-hidden="true"
        style={{
          position:       "fixed",
          bottom:          160,
          left:            10,
          width:           SW_FULL - 20,
          pointerEvents:  "none",
          zIndex:          10,
          display:         "flex",
          flexDirection:  "column",
          gap:             5,
        }}
      >
        {READOUTS.map((r, i) => (
          <div
            key={r.label}
            style={{
              display:        "flex",
              alignItems:     "center",
              gap:             6,
            }}
          >
            {/* Label */}
            <span
              style={{
                fontSize:      9,
                fontFamily:   "var(--chat-font, 'Gill Sans', sans-serif)",
                color:         "var(--lcars-section-title)",
                opacity:       0.75,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                width:          34,
                flexShrink:     0,
                lineHeight:     1,
              }}
            >
              {r.label}
            </span>

            {/* Track */}
            <div
              style={{
                flex:           1,
                height:          7,
                background:     "rgba(255,255,255,0.06)",
                borderRadius:   "0 4px 4px 0",
                overflow:       "hidden",
              }}
            >
              {/* Fill bar — animated via RAF */}
              <div
                ref={el => { barsRef.current[i] = el; }}
                style={{
                  height:         "100%",
                  width:           "50%",
                  background:      "var(--lcars-nav-active)",
                  borderRadius:   "0 4px 4px 0",
                  transition:     "width 0.45s ease, opacity 0.35s ease",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
