"use client";

import { cn } from "@/lib/utils/cn";

export interface DashboardDef {
  uid: string;
  label: string;
}

export const DASHBOARDS: DashboardDef[] = [
  { uid: "mission-control-uid", label: "Mission Control" },
  { uid: "infra-overview", label: "Infrastructure" },
  { uid: "gpu-inference", label: "GPU & Inference" },
  { uid: "system-overview", label: "System Overview" },
  { uid: "training-pipeline", label: "Training Pipeline" },
  { uid: "training-live", label: "Training Live" },
  { uid: "template-performance", label: "Template Scores" },
];

interface DashboardSelectorProps {
  active: string;
  onSelect: (uid: string) => void;
}

export function DashboardSelector({ active, onSelect }: DashboardSelectorProps) {
  return (
    <div className="flex gap-1">
      {DASHBOARDS.map((d) => (
        <button
          key={d.uid}
          onClick={() => onSelect(d.uid)}
          className={cn(
            "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
            active === d.uid
              ? "bg-cyan-600/20 text-cyan-400"
              : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
          )}
        >
          {d.label}
        </button>
      ))}
    </div>
  );
}
