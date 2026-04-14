"use client";

import { useEffect, useState } from "react";
import { fetchTraceDetail } from "@/lib/api/ops";
import { ObservationItem } from "./observation-item";
import { X, ExternalLink } from "lucide-react";
import type { TraceDetail as TraceDetailType, Observation } from "@/types/ops";

interface TraceDetailProps {
  traceId: string;
  onClose: () => void;
}

export function TraceDetail({ traceId, onClose }: TraceDetailProps) {
  const [data, setData] = useState<TraceDetailType | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [activeTab, setActiveTab] = useState<"input" | "output" | "metadata">("input");

  useEffect(() => {
    fetchTraceDetail(traceId).then((d) => {
      if (d) {
        setData(d);
        setObservations(d.observations);
      }
    });
  }, [traceId]);

  if (!data) {
    return (
      <div className="border-t border-[var(--chat-border)] p-6 text-center text-[var(--chat-muted)] text-sm">
        Loading trace...
      </div>
    );
  }

  const trace = data.trace;
  const langfuseUrl = data.langfuse_url || `${window.location.protocol}//${window.location.hostname}:3000/trace/${traceId}`;

  return (
    <div className="border-t border-[var(--chat-accent)]/50 bg-[var(--chat-bg)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-[var(--chat-text)]">{String(trace.name ?? traceId)}</span>
          {trace.latency != null && (
            <span className="text-xs text-[var(--chat-muted)]">{Number(trace.latency).toFixed(2)}s</span>
          )}
          <a
            href={langfuseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)]"
          >
            <ExternalLink size={12} />
          </a>
        </div>
        <button onClick={onClose} className="text-[var(--chat-muted)] hover:text-[var(--chat-text)]">
          <X size={16} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--chat-border)]">
        {(["input", "output", "metadata"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              activeTab === tab
                ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="px-4 py-3 max-h-48 overflow-y-auto">
        <pre className="text-xs text-[var(--chat-text)] whitespace-pre-wrap">
          {activeTab === "input" && JSON.stringify(trace.input, null, 2)}
          {activeTab === "output" && JSON.stringify(trace.output, null, 2)}
          {activeTab === "metadata" && JSON.stringify(trace.metadata, null, 2)}
        </pre>
      </div>

      {/* Observations */}
      {observations.length > 0 && (
        <div className="px-4 py-3 border-t border-[var(--chat-border)] space-y-2">
          <h3 className="text-xs font-medium text-[var(--chat-muted)] mb-2">
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
