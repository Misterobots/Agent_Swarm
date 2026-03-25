"use client";

import { cn } from "@/lib/utils/cn";

export function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
  detail,
  className,
}: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="text-[10px] text-zinc-600 mb-0.5">{label}</p>
      <p className="text-sm font-mono text-zinc-200">{value}</p>
      {detail && <p className="text-[10px] text-zinc-600 mt-0.5">{detail}</p>}
    </div>
  );
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function StatusBanner({
  status,
  label,
  detail,
}: {
  status: "completed" | "failed" | "running" | string;
  label: string;
  detail?: React.ReactNode;
}) {
  const isCompleted = status === "completed";
  const isFailed = status === "failed";

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg text-sm",
        isCompleted && "bg-emerald-500/5 border border-emerald-500/20",
        isFailed && "bg-red-500/5 border border-red-500/20",
        !isCompleted && !isFailed && "bg-amber-500/5 border border-amber-500/20"
      )}
    >
      <span
        className={cn(
          "w-2 h-2 rounded-full",
          isCompleted && "bg-emerald-400",
          isFailed && "bg-red-400",
          !isCompleted && !isFailed && "bg-amber-400 animate-pulse"
        )}
      />
      <span
        className={cn(
          "font-medium",
          isCompleted && "text-emerald-300",
          isFailed && "text-red-300",
          !isCompleted && !isFailed && "text-amber-300"
        )}
      >
        {label}
      </span>
      {detail && <span className="text-zinc-500 ml-auto text-xs">{detail}</span>}
    </div>
  );
}
