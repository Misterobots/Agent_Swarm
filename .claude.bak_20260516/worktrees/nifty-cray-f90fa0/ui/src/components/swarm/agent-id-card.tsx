"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

const ROLE_THEME: Record<string, { accent: string; header: string; avatar: string; text: string; clearance: string }> = {
  researcher: { accent: "#f59e0b", header: "from-amber-900/80 to-amber-800/60",  avatar: "bg-amber-500/10 border-amber-400/60",    text: "text-amber-400",   clearance: "LEVEL 3" },
  architect:  { accent: "#3b82f6", header: "from-blue-900/80 to-blue-800/60",    avatar: "bg-blue-500/10 border-blue-400/60",      text: "text-blue-400",    clearance: "LEVEL 4" },
  coder:      { accent: "#8b5cf6", header: "from-violet-900/80 to-violet-800/60",avatar: "bg-violet-500/10 border-violet-400/60",  text: "text-violet-400",  clearance: "LEVEL 3" },
  devops:     { accent: "#10b981", header: "from-emerald-900/80 to-emerald-800/60",avatar: "bg-emerald-500/10 border-emerald-400/60",text: "text-emerald-400", clearance: "LEVEL 5" },
  analyst:    { accent: "#06b6d4", header: "from-cyan-900/80 to-cyan-800/60",    avatar: "bg-cyan-500/10 border-cyan-400/60",      text: "text-cyan-400",    clearance: "LEVEL 3" },
  verifier:   { accent: "#f43f5e", header: "from-rose-900/80 to-rose-800/60",    avatar: "bg-rose-500/10 border-rose-400/60",      text: "text-rose-400",    clearance: "LEVEL 5" },
};

const DEFAULT_THEME = {
  accent: "#ffffff",
  header: "from-white/10 to-white/5",
  avatar: "bg-white/5 border-white/20",
  text: "text-white/60",
  clearance: "LEVEL 1",
};

/** Deterministic barcode-like bars from worker_id */
function Barcode({ seed }: { seed: string }) {
  const bars = Array.from({ length: 28 }, (_, i) => {
    const c = seed.charCodeAt(i % seed.length) ^ (i * 37);
    return (c % 5 === 0) ? 4 : (c % 3 === 0) ? 2 : 1;
  });
  return (
    <svg viewBox="0 0 80 20" className="w-20 h-5 opacity-30" xmlns="http://www.w3.org/2000/svg">
      {bars.reduce<{ x: number; els: React.ReactElement[] }>(
        ({ x, els }, w, i) => {
          const el = i % 2 === 0
            ? <rect key={i} x={x} y={0} width={w} height={20} fill="currentColor" />
            : <rect key={i} x={x} y={0} width={w} height={20} fill="none" />;
          return { x: x + w + 1, els: [...els, el] };
        },
        { x: 0, els: [] }
      ).els}
    </svg>
  );
}

interface AgentIdCardProps {
  worker: SwarmWorker;
  onDone?: () => void;
}

export function AgentIdCard({ worker, onDone }: AgentIdCardProps) {
  const [stage, setStage] = useState<"hidden" | "hang" | "rest" | "exit">("hidden");
  const scanRef = useRef<HTMLDivElement>(null);
  // Keep a stable ref to onDone so the animation timers are never reset
  // when the parent re-renders as new workers arrive.
  const onDoneRef = useRef(onDone);
  useEffect(() => { onDoneRef.current = onDone; }, [onDone]);
  const role = worker.role?.toLowerCase() ?? "";
  const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
  const badgeNum = (worker.worker_id ?? "").replace(/[^a-z0-9]/gi, "").slice(-6).toUpperCase().padStart(6, "0");

  useEffect(() => {
    // Stagger: hidden → hang (drop in with pendulum) → rest → scan → exit
    // Empty deps: timers are set once on mount and never reset mid-animation.
    const t0 = setTimeout(() => setStage("hang"),  80);
    const t1 = setTimeout(() => setStage("rest"),  600);
    const t2 = setTimeout(() => setStage("exit"), 4000);
    const t3 = setTimeout(() => onDoneRef.current?.(), 4600);
    return () => { clearTimeout(t0); clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Trigger scan-light sweep once card is at rest
  useEffect(() => {
    if (stage === "rest" && scanRef.current) {
      scanRef.current.style.animation = "id-scan 1.1s ease-in-out 0.3s 1 forwards";
    }
  }, [stage]);

  return (
    <div className="flex flex-col items-center justify-center w-full h-full gap-0">
      {/* Lanyard string */}
      <div
        className={cn(
          "w-px bg-white/20 transition-all duration-500",
          stage === "hidden" ? "h-0 opacity-0" : "h-10 opacity-100",
        )}
      />

      {/* Badge wrapper — pendulum drop */}
      <div
        className={cn(
          "relative transition-all",
          stage === "hidden" && "opacity-0 -translate-y-16",
          stage === "hang"   && "opacity-100 -translate-y-2 [animation:id-badge-swing_0.55s_ease-out_forwards]",
          stage === "rest"   && "opacity-100 translate-y-0",
          stage === "exit"   && "opacity-0 translate-y-14 scale-50 duration-500",
          stage !== "hidden" && stage !== "exit" && "duration-[420ms] ease-[cubic-bezier(.32,1.4,.64,1)]",
        )}
      >
        {/* Punch-hole clip */}
        <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-0.5">
          <div className="w-3 h-3 rounded-full bg-[var(--chat-bg,#0d0f1a)] border-2 border-white/30 shadow-inner" />
          <div className="w-px h-2 bg-white/20" />
        </div>

        {/* Card */}
        <div
          className="relative w-[min(268px,82vw)] rounded-xl overflow-hidden"
          style={{
            background: "linear-gradient(160deg, var(--chat-panel) 0%, var(--chat-surface) 60%, var(--chat-bg) 100%)",
            border: `1px solid ${theme.accent}33`,
            boxShadow: `0 24px 64px rgba(0,0,0,0.5), 0 0 0 1px ${theme.accent}18, inset 0 1px 0 rgba(255,255,255,0.04)`,
          }}
        >
          {/* Colorful spawn flash — role-colored radial burst on card entry */}
          {stage === "hang" && (
            <div
              className="absolute inset-0 rounded-xl pointer-events-none z-20 [animation:id-spawn-flash_0.85s_ease-out_forwards]"
              style={{
                background: `radial-gradient(ellipse at 50% 40%, ${theme.accent}80 0%, ${theme.accent}30 35%, transparent 65%)`,
                boxShadow: `inset 0 0 40px 8px ${theme.accent}50`,
              }}
            />
          )}
          {/* Holographic foil stripe — top edge */}
          <div
            className="h-1 w-full"
            style={{
              background: `linear-gradient(90deg, transparent 0%, ${theme.accent} 20%, #fff 50%, ${theme.accent} 80%, transparent 100%)`,
              opacity: 0.85,
            }}
          />

          {/* Org header */}
          <div
            className={cn("px-4 py-2.5 bg-gradient-to-r border-b", theme.header)}
            style={{ borderColor: `${theme.accent}25` }}
          >
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-black tracking-[0.3em] text-white/50 uppercase">Memex</span>
              <span className="text-[8px] font-mono tracking-widest" style={{ color: `${theme.accent}99` }}>PIONEER DIVISION</span>
            </div>
            <div className="text-[8px] font-mono text-white/25 mt-0.5 tracking-wider">AGENT CREDENTIAL • ACTIVE SESSION</div>
          </div>

          {/* Main body — horizontal layout like a real ID */}
          <div className="flex gap-3 px-4 pt-4 pb-3">
            {/* Photo zone */}
            <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
              <div
                className={cn(
                  "relative w-[72px] h-[88px] rounded-md flex items-center justify-center border overflow-hidden",
                  theme.avatar,
                )}
                style={{ boxShadow: `0 0 16px ${theme.accent}30` }}
              >
                <div className={cn("w-full h-full", theme.text)}>
                  <PioneerPortrait role={role} />
                </div>
                {/* Live indicator dot */}
                <span
                  className="absolute top-1 right-1 w-2 h-2 rounded-full animate-pulse"
                  style={{ background: theme.accent, boxShadow: `0 0 6px ${theme.accent}` }}
                />
              </div>
              <span className="text-[7px] font-mono text-white/20 tracking-widest">PHOTO ID</span>
            </div>

            {/* Info zone */}
            <div className="flex flex-col justify-between flex-1 min-w-0 py-0.5">
              {/* Name */}
              <div>
                <p className="font-black text-[var(--chat-text)] text-sm leading-tight tracking-tight truncate">
                  {worker.pioneer_name ?? role}
                </p>
                <p className="text-[10px] text-[var(--chat-muted)] font-medium truncate leading-tight">
                  {worker.pioneer_full_name && worker.pioneer_full_name !== worker.pioneer_name
                    ? worker.pioneer_full_name
                    : ""}
                </p>
              </div>

              {/* Role badge */}
              <div
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm self-start mt-1"
                style={{ background: `${theme.accent}18`, border: `1px solid ${theme.accent}40` }}
              >
                <span className="text-[9px] font-bold uppercase tracking-[0.15em]" style={{ color: theme.accent }}>
                  {worker.role}
                </span>
              </div>

              {/* Clearance + phase */}
              <div className="mt-2 space-y-0.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-[7px] font-mono text-[var(--chat-muted)] uppercase tracking-wider">Clearance</span>
                  <span className="text-[7px] font-mono font-bold" style={{ color: `${theme.accent}cc` }}>{theme.clearance}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[7px] font-mono text-[var(--chat-muted)] uppercase tracking-wider">Phase</span>
                  <span className="text-[7px] font-mono text-[var(--chat-muted)] uppercase">{worker.phase ?? "active"}</span>
                </div>
              </div>

              {/* Badge number */}
              <p className="text-[8px] font-mono text-[var(--chat-muted)] opacity-50 mt-1 tracking-widest"># {badgeNum}</p>
            </div>
          </div>

          {/* Motto strip */}
          {worker.pioneer_motto && (
            <div
              className="mx-4 mb-3 px-2.5 py-1.5 rounded-sm"
              style={{ background: `${theme.accent}0c`, borderLeft: `2px solid ${theme.accent}50` }}
            >
              <p className="text-[9px] text-[var(--chat-muted)] italic leading-snug">
                &ldquo;{worker.pioneer_motto}&rdquo;
              </p>
            </div>
          )}

          {/* Machine-readable / barcode zone */}
          <div
            className="px-4 py-2.5 border-t flex items-center justify-between"
            style={{ borderColor: `${theme.accent}15`, background: "var(--chat-soft)" }}
          >
            <div className={cn("flex items-center", theme.text)}>
              <Barcode seed={worker.worker_id ?? "000000"} />
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ background: theme.accent }}
              />
              <span className="text-[8px] font-bold tracking-wider" style={{ color: theme.accent }}>ACTIVE</span>
            </div>
          </div>

          {/* Scan-light sweep overlay */}
          <div
            ref={scanRef}
            className="absolute inset-0 pointer-events-none"
            style={{
              background: `linear-gradient(180deg, transparent 0%, ${theme.accent}18 50%, transparent 100%)`,
              transform: "translateY(-100%)",
              opacity: 0,
            }}
          />

          {/* Scanline texture */}
          <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,#fff_2px,#fff_4px)]" />

          {/* Holographic corner shimmer */}
          <div
            className="absolute top-0 right-0 w-16 h-16 pointer-events-none"
            style={{
              background: `conic-gradient(from 45deg, transparent, ${theme.accent}30, transparent, ${theme.accent}15, transparent)`,
              opacity: 0.6,
              borderRadius: "0 0 0 100%",
            }}
          />
        </div>
      </div>
    </div>
  );
}
