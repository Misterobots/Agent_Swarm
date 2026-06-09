"use client";

import { useState } from "react";
import { Palette, Code2, ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { WorkflowNextStep } from "@/types/chat";

interface WorkflowActionsCardProps {
  steps: WorkflowNextStep[];
  onSend?: (text: string) => void;
}

const STEP_CONFIG: Record<string, { icon: React.ReactNode; accent: string; bg: string; border: string }> = {
  design: {
    icon: <Palette size={16} />,
    accent: "text-purple-300",
    bg: "bg-purple-950/30 hover:bg-purple-950/50",
    border: "border-purple-500/30 hover:border-purple-500/60",
  },
  swarm: {
    icon: <Code2 size={16} />,
    accent: "text-cyan-300",
    bg: "bg-cyan-950/30 hover:bg-cyan-950/50",
    border: "border-cyan-500/30 hover:border-cyan-500/60",
  },
};

export function WorkflowActionsCard({ steps, onSend }: WorkflowActionsCardProps) {
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const setDesignMode  = useSettingsStore((s) => s.setDesignMode);
  const setSwarmMode   = useSettingsStore((s) => s.setSwarmMode);
  const setWorkshopMode = useSettingsStore((s) => s.setWorkshopMode);

  const handleStep = (step: WorkflowNextStep) => {
    if (!onSend || pendingMode) return;
    setPendingMode(step.mode);
    // Switch to the right mode and clear workshop mode
    setWorkshopMode(false);
    if (step.mode === "design") {
      setDesignMode(true);
      setSwarmMode(false);
      // Prefix with /design so the backend slash-command parser forces design_mode
      // and clears workshop_mode server-side, regardless of what mode flags the
      // stale closure may have baked into the request.
      onSend(`/design ${step.prompt}`);
    } else if (step.mode === "swarm") {
      setSwarmMode(true);
      setDesignMode(false);
      onSend(`/swarm ${step.prompt}`);
    } else {
      onSend(step.prompt);
    }
  };

  return (
    <div className="mt-4 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-elevated)] overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--chat-border)]">
        <span className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wide">
          Continue the Pipeline
        </span>
      </div>
      <div className={cn("p-2", steps.length > 1 ? "grid grid-cols-2 gap-2" : "")}>
        {steps.map((step) => {
          const cfg = STEP_CONFIG[step.mode] ?? STEP_CONFIG.design;
          return (
            <button
              key={step.mode}
              type="button"
              onClick={() => handleStep(step)}
              disabled={!onSend || pendingMode !== null}
              className={cn(
                "group flex items-center gap-3 w-full rounded-md border px-4 py-3 transition-all text-left disabled:opacity-60 disabled:cursor-not-allowed",
                cfg.bg, cfg.border,
              )}
            >
              <span className={cn("shrink-0", cfg.accent)}>
                {pendingMode === step.mode ? <Loader2 size={16} className="animate-spin" /> : cfg.icon}
              </span>
              <span className="flex-1 min-w-0">
                <span className={cn("block text-sm font-semibold", cfg.accent)}>
                  {pendingMode === step.mode ? "Sending…" : step.label}
                </span>
                <span className="block text-[11px] text-[var(--chat-muted)] truncate mt-0.5">
                  {step.mode === "design" ? "Generate a visual mockup" : "Multi-agent implementation"}
                </span>
              </span>
              {pendingMode !== step.mode && (
                <ArrowRight size={14} className={cn("shrink-0 opacity-40 group-hover:opacity-100 transition-opacity", cfg.accent)} />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
