"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: string;
  icon: LucideIcon;
  status?: "ok" | "warn" | "error";
}

export function MetricCard({ label, value, delta, icon: Icon, status = "ok" }: MetricCardProps) {
  return (
    <div className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-[var(--chat-muted)] uppercase tracking-wide">{label}</span>
        <Icon
          size={16}
          className={cn(
            status === "ok" && "text-emerald-400",
            status === "warn" && "text-yellow-400",
            status === "error" && "text-red-400"
          )}
        />
      </div>
      <div className="text-2xl font-semibold text-[var(--chat-text)]">{value}</div>
      {delta && (
        <div className="text-xs text-[var(--chat-muted)] mt-1">{delta}</div>
      )}
    </div>
  );
}
