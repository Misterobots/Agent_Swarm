"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { Observation } from "@/types/ops";

interface ObservationItemProps {
  observation: Observation;
}

export function ObservationItem({ observation: obs }: ObservationItemProps) {
  const [expanded, setExpanded] = useState(false);

  const duration =
    obs.startTime && obs.endTime
      ? ((new Date(obs.endTime).getTime() - new Date(obs.startTime).getTime()) / 1000).toFixed(2)
      : null;

  const tokens = obs.usage
    ? `In: ${obs.usage.input ?? 0} Out: ${obs.usage.output ?? 0}`
    : null;

  return (
    <div className="border border-zinc-800/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-800/30 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-zinc-500" />
        ) : (
          <ChevronRight size={14} className="text-zinc-500" />
        )}
        <span
          className={cn(
            "px-1.5 py-0.5 rounded text-[10px] font-mono",
            obs.type === "GENERATION"
              ? "bg-violet-900/30 text-violet-400"
              : "bg-zinc-800 text-zinc-400"
          )}
        >
          {obs.type}
        </span>
        <span className="text-zinc-300 flex-1 truncate">{obs.name}</span>
        {duration && (
          <span className="text-xs text-zinc-500">{duration}s</span>
        )}
        {obs.model && (
          <span className="text-xs text-cyan-600">{obs.model}</span>
        )}
        {tokens && (
          <span className="text-xs text-zinc-600">{tokens}</span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-zinc-800/50 px-4 py-3 space-y-3 text-xs">
          {obs.input != null && (
            <div>
              <div className="text-zinc-500 mb-1 font-medium">Input</div>
              <pre className="bg-[#0a0a14] p-2 rounded text-zinc-300 overflow-x-auto max-h-40 overflow-y-auto">
                {typeof obs.input === "string"
                  ? obs.input
                  : JSON.stringify(obs.input, null, 2)}
              </pre>
            </div>
          )}
          {obs.output != null && (
            <div>
              <div className="text-zinc-500 mb-1 font-medium">Output</div>
              <pre className="bg-[#0a0a14] p-2 rounded text-zinc-300 overflow-x-auto max-h-40 overflow-y-auto">
                {typeof obs.output === "string"
                  ? obs.output
                  : JSON.stringify(obs.output, null, 2)}
              </pre>
            </div>
          )}
          {obs.usage?.totalCost != null && (
            <div className="text-zinc-500">
              Cost: ${obs.usage.totalCost.toFixed(4)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
