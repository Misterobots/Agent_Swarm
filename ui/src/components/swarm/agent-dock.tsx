"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

const ROLE_THEME: Record<string, { text: string; bg: string; border: string; stripe: string }> = {
  researcher: { text: "text-amber-400",   bg: "bg-amber-500/15",   border: "border-amber-500/40",   stripe: "bg-amber-400" },
  architect:  { text: "text-blue-400",    bg: "bg-blue-500/15",    border: "border-blue-500/40",    stripe: "bg-blue-400" },
  coder:      { text: "text-violet-400",  bg: "bg-violet-500/15",  border: "border-violet-500/40",  stripe: "bg-violet-400" },
  devops:     { text: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/40", stripe: "bg-emerald-400" },
  analyst:    { text: "text-cyan-400",    bg: "bg-cyan-500/15",    border: "border-cyan-500/40",    stripe: "bg-cyan-400" },
  verifier:   { text: "text-rose-400",    bg: "bg-rose-500/15",    border: "border-rose-500/40",    stripe: "bg-rose-400" },
};
const DEFAULT_THEME = { text: "text-[var(--chat-muted)]", bg: "bg-[var(--chat-soft)]", border: "border-[var(--chat-border)]", stripe: "bg-[var(--chat-muted)]" };

/** Role-specific activity verbs that cycle while the agent works */
const ROLE_ACTIONS: Record<string, string[]> = {
  researcher: ["Researching", "Gathering", "Scanning", "Reading", "Querying"],
  architect:  ["Designing", "Planning", "Structuring", "Modeling", "Drafting"],
  coder:      ["Coding", "Writing", "Implementing", "Building", "Refining"],
  devops:     ["Deploying", "Configuring", "Provisioning", "Monitoring", "Optimizing"],
  analyst:    ["Analyzing", "Evaluating", "Processing", "Parsing", "Assessing"],
  verifier:   ["Verifying", "Checking", "Testing", "Validating", "Confirming"],
};
const FALLBACK_ACTIONS = ["Analyzing", "Reasoning", "Connecting", "Evaluating", "Working"];

interface AgentDockProps {
  workers: SwarmWorker[];
  onSelect?: (id: string) => void;
}

export function AgentDock({ workers, onSelect }: AgentDockProps) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1800);
    return () => clearInterval(id);
  }, []);

  // Show up to 3 active workers; pad with placeholders
  const active = workers.filter((w) => w.state === "running" || w.state === "pending");
  const display = active.slice(0, 3);

  if (display.length === 0) return null;

  return (
    <div className="flex items-center justify-center gap-4 w-full py-4 px-3 flex-wrap">
      {display.map((w, i) => {
        const isRunning = w.state === "running";
        const role = w.role?.toLowerCase() ?? "";
        const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
        const actions = ROLE_ACTIONS[role] ?? FALLBACK_ACTIONS;
        const status = isRunning ? actions[(tick + i) % actions.length] : "Queued";

        return (
          <div
            key={w.worker_id}
            onClick={() => onSelect?.(w.worker_id)}
            className={cn(
              "flex flex-col items-center gap-2 px-5 py-4 rounded-2xl transition-all min-w-[6rem]",
              "border",
              onSelect && "cursor-pointer",
              isRunning
                ? cn(theme.bg, theme.border, onSelect && "hover:brightness-110")
                : cn("bg-[var(--chat-soft)]/40 border-[var(--chat-border)]", onSelect && "hover:bg-[var(--chat-soft)]"),
            )}
          >
            {/* Portrait — always full role color; pending state shown by card bg */}
            <div className={cn(
              "relative w-12 h-12 rounded-full flex items-center justify-center border-2 overflow-hidden",
              theme.bg, theme.border, theme.text,
            )}>
              <PioneerPortrait role={role} />
              {isRunning && (
                <span className={cn(
                  "absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[var(--chat-bg)] animate-pulse",
                  theme.stripe,
                )} />
              )}
            </div>

            <p className="text-[11px] font-semibold text-[var(--chat-text)] text-center leading-none">{w.pioneer_name}</p>
            <p className={cn("text-[9px] font-bold capitalize tracking-wide", theme.text)}>{w.role}</p>
            <p
              key={status}
              className={cn(
                "text-[9px] font-bold tracking-wider transition-all duration-300 uppercase",
                isRunning ? theme.text : "text-[var(--chat-muted)]",
              )}
            >
              {status}
            </p>
          </div>
        );
      })}
    </div>
  );
}
