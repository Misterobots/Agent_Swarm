"use client";

import { useEffect, useState } from "react";
import { fetchTraceDetail, fetchObservations } from "@/lib/api/ops";
import { ObservationItem } from "./observation-item";
import { X, ExternalLink } from "lucide-react";
import type { LangfuseTraceDetail, LangfuseObservation } from "@/types/ops";

interface TraceDetailProps {
  traceId: string;
  onClose: () => void;
}

export function TraceDetail({ traceId, onClose }: TraceDetailProps) {
  const [trace, setTrace] = useState<LangfuseTraceDetail | null>(null);
  const [observations, setObservations] = useState<LangfuseObservation[]>([]);
  const [activeTab, setActiveTab] = useState<"input" | "output" | "metadata">("input");

  useEffect(() => {
    fetchTraceDetail(traceId).then(setTrace);
    fetchObservations(traceId).then(setObservations);
  }, [traceId]);

  if (!trace) {
    return (
      <div className="border-t border-zinc-800 p-6 text-center text-zinc-500 text-sm">
        Loading trace...
      </div>
    );
  }

  const langfuseUrl = `${window.location.protocol}//${window.location.hostname}:3000/trace/${traceId}`;

  return (
    <div className="border-t border-cyan-800/50 bg-[#0f0f1a]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-zinc-200">{trace.name}</span>
          {trace.latency != null && (
            <span className="text-xs text-zinc-500">{trace.latency.toFixed(2)}s</span>
          )}
          <a
            href={langfuseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-cyan-600 hover:text-cyan-400"
          >
            <ExternalLink size={12} />
          </a>
        </div>
        <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
          <X size={16} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800">
        {(["input", "output", "metadata"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              activeTab === tab
                ? "text-cyan-400 border-b-2 border-cyan-400"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="px-4 py-3 max-h-48 overflow-y-auto">
        <pre className="text-xs text-zinc-300 whitespace-pre-wrap">
          {activeTab === "input" && (
            typeof trace.input === "string" ? trace.input : JSON.stringify(trace.input, null, 2)
          )}
          {activeTab === "output" && (
            typeof trace.output === "string" ? trace.output : JSON.stringify(trace.output, null, 2)
          )}
          {activeTab === "metadata" && JSON.stringify(trace.metadata, null, 2)}
        </pre>
      </div>

      {/* Observations */}
      {observations.length > 0 && (
        <div className="px-4 py-3 border-t border-zinc-800 space-y-2">
          <h3 className="text-xs font-medium text-zinc-400 mb-2">
            Observations ({observations.length})
          </h3>
          {observations.map((obs) => (
            <ObservationItem key={obs.id} observation={obs} />
          ))}
        </div>
      )}
    </div>
  );
}
