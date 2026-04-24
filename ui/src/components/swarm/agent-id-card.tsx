"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

const ROLE_THEME: Record<string, { stripe: string; avatar: string; text: string; glow: string }> = {
  researcher: { stripe: "from-amber-400 via-amber-300 to-orange-400",   avatar: "bg-amber-500/10 border-amber-500/50",    text: "text-amber-400",   glow: "shadow-amber-500/20" },
  architect:  { stripe: "from-blue-400 via-blue-300 to-cyan-400",       avatar: "bg-blue-500/10 border-blue-500/50",      text: "text-blue-400",    glow: "shadow-blue-500/20" },
  coder:      { stripe: "from-violet-400 via-violet-300 to-purple-400", avatar: "bg-violet-500/10 border-violet-500/50",  text: "text-violet-400",  glow: "shadow-violet-500/20" },
  devops:     { stripe: "from-emerald-400 via-emerald-300 to-teal-400", avatar: "bg-emerald-500/10 border-emerald-500/50", text: "text-emerald-400", glow: "shadow-emerald-500/20" },
  analyst:    { stripe: "from-cyan-400 via-cyan-300 to-blue-400",       avatar: "bg-cyan-500/10 border-cyan-500/50",      text: "text-cyan-400",    glow: "shadow-cyan-500/20" },
  verifier:   { stripe: "from-rose-400 via-rose-300 to-pink-400",       avatar: "bg-rose-500/10 border-rose-500/50",      text: "text-rose-400",    glow: "shadow-rose-500/20" },
};

const DEFAULT_THEME = {
  stripe: "from-white/40 to-white/20",
  avatar: "bg-white/5 border-white/20",
  text: "text-white/60",
  glow: "shadow-white/5",
};

interface AgentIdCardProps {
  worker: SwarmWorker;
  onDone?: () => void;
}

export function AgentIdCard({ worker, onDone }: AgentIdCardProps) {
  const [stage, setStage] = useState<"drop" | "straight" | "exit">("drop");
  const role = worker.role?.toLowerCase() ?? "";
  const theme = ROLE_THEME[role] ?? DEFAULT_THEME;

  useEffect(() => {
    const t1 = setTimeout(() => setStage("straight"), 400);
    const t2 = setTimeout(() => setStage("exit"), 3400);
    const t3 = setTimeout(() => onDone?.(), 3900);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [onDone]);

  return (
    <div className="flex items-center justify-center w-full h-full">
      <div
        className={cn(
          "relative w-72 rounded-2xl overflow-hidden transition-all",
          "duration-500 ease-[cubic-bezier(.32,1.4,.64,1)]",
          "bg-[var(--chat-surface)] border border-white/10",
          "shadow-[0_28px_72px_rgba(0,0,0,0.75)]",
          stage === "drop"     && "opacity-0 -translate-y-10 rotate-[-6deg] scale-90",
          stage === "straight" && "opacity-100 translate-y-0 rotate-0 scale-100",
          stage === "exit"     && "opacity-0 translate-y-6 scale-90 rotate-[3deg]",
        )}
      >
        {/* Role colour stripe */}
        <div className={cn("h-1.5 w-full bg-gradient-to-r", theme.stripe)} />

        {/* Header bar */}
        <div className="flex items-center px-4 py-2.5 border-b border-white/6">
          <span className="text-[10px] font-black tracking-[0.25em] text-white/35 uppercase">Memex</span>
          <span className="ml-auto text-[9px] font-mono text-white/20 tracking-widest">PIONEER ID</span>
        </div>

        {/* Body */}
        <div className="px-6 pb-6 pt-6 flex flex-col items-center gap-4">
          {/* Avatar */}
          <div className={cn(
            "relative w-24 h-24 rounded-full flex items-center justify-center border-2 shadow-xl overflow-hidden",
            theme.avatar,
            theme.glow,
            theme.text,
          )}>
            <PioneerPortrait role={role} />
            <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-emerald-400 border-2 border-[var(--chat-surface)] animate-pulse" />
          </div>

          {/* Full name + role */}
          <div className="text-center">
            <p className="font-black text-[var(--chat-text)] text-base leading-tight tracking-tight">
              {worker.pioneer_full_name ?? worker.pioneer_name}
            </p>
            <p className={cn("text-[11px] mt-1.5 uppercase tracking-[0.18em] font-bold", theme.text)}>
              {worker.role}
            </p>
          </div>

          {/* Motto */}
          {worker.pioneer_motto && (
            <p className="text-[var(--chat-muted)] text-[11px] text-center leading-snug italic px-1">
              &ldquo;{worker.pioneer_motto}&rdquo;
            </p>
          )}

          <div className="w-full h-px bg-white/6" />

          {/* Footer */}
          <div className="w-full flex items-center justify-between">
            <span className="text-white/20 text-[9px] font-mono tracking-widest uppercase">Agent Swarm</span>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400 text-[9px] font-bold tracking-wide">ACTIVE</span>
            </div>
          </div>
        </div>

        {/* Subtle scanline overlay */}
        <div className="absolute inset-0 pointer-events-none bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(255,255,255,0.012)_2px,rgba(255,255,255,0.012)_4px)]" />
      </div>
    </div>
  );
}
