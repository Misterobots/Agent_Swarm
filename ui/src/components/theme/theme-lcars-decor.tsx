"use client";

import { useEffect, useRef, useState } from "react";
import { useSettingsStore } from "@/lib/stores/settings-store";

const RIGHT_PILLS = [
  { label: "02-110", color: "var(--lcars-elbow-d)", h: 80, isData: false },
  { label: "MEM", color: "var(--lcars-elbow-b)", h: 60, isData: true, seedA: 0.0013, seedB: 0.0 },
  { label: "L-R", color: "var(--lcars-elbow-a)", h: 120, isData: false },
  { label: "COM", color: "var(--lcars-elbow-c)", h: 45, isData: true, seedA: 0.0009, seedB: 2.1 },
  { label: "SNS", color: "var(--lcars-elbow-b)", h: 45, isData: true, seedA: 0.0017, seedB: 4.4 },
  { label: "47-B", color: "var(--lcars-elbow-a)", h: 180, isData: false },
];

export function ThemeLCARSDecor() {
  const theme = useSettingsStore(s => s.theme);
  const isLCARS = theme.startsWith("lcars");
  const barsRef = useRef<(HTMLDivElement | null)[]>([]);
  const chaserRefs = useRef<(HTMLDivElement | null)[]>([]);
  const textRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const rafRef = useRef<number>(0);
  const [metrics, setMetrics] = useState({
    topHeight: 90,
    bottomHeight: 113,
    sidebarWidth: 260
  });

  useEffect(() => {
    if (!isLCARS) return;
    
    // Dynamically track the Logo Block and Footer Block heights
    const observer = new ResizeObserver(() => {
      const wrapper = document.querySelector('.sidebar-wrapper');
      if (wrapper) {
        const rect = wrapper.getBoundingClientRect();
        
        let topH = 90;
        const logo = wrapper.firstElementChild;
        if (logo) topH = logo.getBoundingClientRect().height;
        
        let botH = 113;
        const footer = wrapper.lastElementChild;
        if (footer) botH = footer.getBoundingClientRect().height;
        
        setMetrics({
          topHeight: topH,
          bottomHeight: botH,
          sidebarWidth: rect.width
        });
      }
    });

    const wrapper = document.querySelector('.sidebar-wrapper');
    if (wrapper) {
      observer.observe(wrapper);
      if (wrapper.firstElementChild) observer.observe(wrapper.firstElementChild);
      if (wrapper.lastElementChild) observer.observe(wrapper.lastElementChild);
    }
    
    let running = true;
    const loop = (ts: number) => {
      if (!running) return;
      
      // Snappy right-hand bars (jumping values instead of smooth sine)
      RIGHT_PILLS.forEach((pill, i) => {
        if (pill.isData) {
          const bar = barsRef.current[i];
          if (!bar) return;
          const step = Math.floor(ts / (150 + i * 30));
          const level = 0.15 + Math.abs(Math.sin(step * (pill.seedA || 1.1) + (pill.seedB || 0))) * 0.85;
          bar.style.height = `${Math.round(level * 100)}%`;
        }
      });

      // Chaser sequence in top bar (blinking lights)
      const chaserIndex = Math.floor(ts / 100) % 6;
      chaserRefs.current.forEach((el, i) => {
         if (!el) return;
         el.style.opacity = i === chaserIndex ? "1" : "0.2";
      });

      // Rapidly changing diagnostic numbers
      const diagStep = Math.floor(ts / 60);
      if (diagStep % 2 === 0) {
        textRefs.current.forEach((el, i) => {
          if (!el) return;
          const val = Math.floor(Math.abs(Math.sin(diagStep + i * 13.37)) * 99999);
          el.innerText = val.toString().padStart(5, "0");
        });
      }

      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => { 
      running = false; 
      cancelAnimationFrame(rafRef.current); 
      observer.disconnect();
    };
  }, [isLCARS]);

  if (!isLCARS) return null;

  return (
    <>
      {/* TOP HORIZONTAL BAR (Header Sweep) */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          top: 12,
          left: metrics.sidebarWidth, // Connects perfectly to the right edge of sidebar items
          right: 90, // Leaves room for right column
          height: 24, // Minimal horizontal bar
          background: "var(--lcars-elbow-a)",
          zIndex: 40,
          pointerEvents: "none",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0 20px",
          borderBottomLeftRadius: 16,
          boxShadow: "inset -4px -4px 16px rgba(0,0,0,0.4)",
        }}
      >
        <div style={{ display: "flex", gap: 16, alignItems: "center", height: "100%" }}>
          <span style={{ 
            color: "var(--lcars-nav-text-on)", 
            fontFamily: "'Antonio', 'Arial Narrow', sans-serif",
            fontWeight: 900,
            fontSize: 14,
            letterSpacing: "0.15em",
            display: "flex",
            alignItems: "center",
            gap: 16
          }}>
            LCARS-47 <span ref={el => { textRefs.current[0] = el; }} style={{ fontSize: 11, opacity: 0.7, letterSpacing: "0.05em" }}>00000</span>
          </span>
          {/* Diagnostic Chaser Sequence */}
          <div style={{ display: "flex", gap: 4, height: 8 }}>
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} ref={el => { chaserRefs.current[i] = el; }} style={{ width: 12, background: "var(--lcars-elbow-b)", borderRadius: "4px" }} />
            ))}
          </div>
        </div>
        <div style={{ display: "flex", gap: 4, height: "100%" }}>
          <div style={{ width: 40, background: "#000" }} />
          <div style={{ width: 12, background: "var(--lcars-elbow-d)" }} />
          <div style={{ width: 12, background: "var(--lcars-elbow-b)" }} />
        </div>
      </div>

      {/* BOTTOM HORIZONTAL BAR (Footer Sweep) */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          bottom: 12,
          left: metrics.sidebarWidth,
          right: 90,
          height: 24, // Minimal horizontal bar
          background: "var(--lcars-elbow-c)",
          zIndex: 40,
          pointerEvents: "none",
          borderTopLeftRadius: 16,
          boxShadow: "inset -4px -4px 16px rgba(0,0,0,0.4)",
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          paddingRight: 16
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 24, height: 6, background: "var(--lcars-elbow-d)", borderRadius: 3 }} />
          <span ref={el => { textRefs.current[1] = el; }} style={{ 
            color: "var(--lcars-nav-text-on)", 
            fontFamily: "'Antonio', 'Arial Narrow', sans-serif",
            fontWeight: 900,
            fontSize: 10,
            letterSpacing: "0.1em",
            opacity: 0.7
          }}>
            00000
          </span>
        </div>
      </div>

      {/* RIGHT VERTICAL STACK */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          top: 12,
          right: 12,
          bottom: 12,
          width: 70,
          zIndex: 40,
          pointerEvents: "none",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {/* Top curved cap */}
        <div style={{ 
          background: "var(--lcars-elbow-c)", 
          height: 120,
          borderRadius: "0 30px 0 0",
          borderBottomLeftRadius: 40,
          boxShadow: "inset -4px -4px 16px rgba(0,0,0,0.4)",
        }} />

        {RIGHT_PILLS.map((pill, i) => (
          <div
            key={i}
            style={{
              background: pill.color,
              height: pill.h,
              borderRadius: "20px 0 0 20px",
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "flex-start",
              paddingBottom: 8,
              paddingLeft: 8,
              boxSizing: "border-box",
              boxShadow: "inset -4px -4px 16px rgba(0,0,0,0.4)",
              position: "relative",
              overflow: "hidden"
            }}
          >
            {pill.isData && (
              <div 
                ref={el => { barsRef.current[i] = el; }}
                style={{
                  position: "absolute",
                  bottom: 0,
                  left: 24,
                  width: 8,
                  height: "50%",
                  background: "rgba(0,0,0,0.3)",
                  borderRadius: "4px 4px 0 0",
                  transition: "height 0.08s linear"
                }}
              />
            )}
            <span style={{
              color: "var(--lcars-nav-text-on)",
              fontFamily: "'Antonio', 'Arial Narrow', sans-serif",
              fontWeight: 800,
              fontSize: 14,
              letterSpacing: "0.1em",
              writingMode: "vertical-rl",
              transform: "rotate(180deg)",
              position: "relative",
              zIndex: 2
            }}>
              {pill.label}
            </span>
          </div>
        ))}

        {/* Bottom curved cap */}
        <div style={{ 
          background: "var(--lcars-elbow-d)", 
          flex: 1, // Fills remaining space
          borderRadius: "0 0 30px 0",
          borderTopLeftRadius: 40,
          boxShadow: "inset -4px -4px 16px rgba(0,0,0,0.4)",
        }} />
      </div>
    </>
  );
}
