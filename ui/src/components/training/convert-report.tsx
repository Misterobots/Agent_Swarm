"use client";

import { useEffect, useState } from "react";
import { fetchConvertReport, type ConvertReport } from "@/lib/api/training";
import {
  Clock,
  Server,
  AlertTriangle,
  Loader2,
  Package,
  CheckCircle2,
} from "lucide-react";
import { Section, Stat, StatusBanner, formatDuration } from "./report-helpers";

export function ConvertReportView({
  runId,
  pollInterval = 5000,
}: {
  runId: number;
  pollInterval?: number;
}) {
  const [report, setReport] = useState<ConvertReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      const r = await fetchConvertReport(runId);
      if (!active) return;
      if (r) {
        setReport(r);
        setLoading(false);
      }
    };
    poll();
    // Poll while conversion may still be running
    const interval = setInterval(poll, pollInterval);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [runId, pollInterval]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-[var(--chat-muted)] text-sm">
        <Loader2 size={14} className="animate-spin" />
        Converting model...
      </div>
    );
  }

  if (!report) {
    return (
      <p className="text-sm text-[var(--chat-muted)] py-4">
        Conversion report unavailable.
      </p>
    );
  }

  const t = report.timing;

  return (
    <div className="space-y-4 mt-3">
      {/* Status */}
      <StatusBanner
        status={report.status}
        label={
          report.status === "completed"
            ? "Conversion Completed"
            : report.status === "failed"
            ? "Conversion Failed"
            : "Conversion In Progress"
        }
        detail={
          report.method
            ? `Method: ${report.method === "gguf" ? "GGUF (Q4_K_M)" : "Safetensors Direct"}`
            : undefined
        }
      />

      {/* Error */}
      {report.error && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={12} className="text-red-400" />
            <p className="text-xs font-medium text-red-400">Error</p>
          </div>
          <p className="text-xs text-red-300/80 font-mono whitespace-pre-wrap">
            {report.error}
          </p>
        </div>
      )}

      {/* Warnings */}
      {report.warnings.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3 space-y-1">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={12} className="text-amber-400" />
            <p className="text-xs font-medium text-amber-400">Warnings</p>
          </div>
          {report.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-300/80">
              {w}
            </p>
          ))}
        </div>
      )}

      {/* Timing */}
      {(t.total_sec != null || t.merge_sec != null) && (
        <Section
          icon={<Clock size={14} className="text-cyan-500" />}
          title="Timing"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat
              label="Total"
              value={t.total_sec != null ? formatDuration(t.total_sec) : "—"}
            />
            <Stat
              label="LoRA Merge"
              value={t.merge_sec != null ? formatDuration(t.merge_sec) : "—"}
            />
            <Stat
              label="Convert/Quantize"
              value={t.convert_sec != null ? formatDuration(t.convert_sec) : "—"}
            />
            <Stat
              label="Ollama Import"
              value={
                t.ollama_import_sec != null
                  ? formatDuration(t.ollama_import_sec)
                  : "—"
              }
            />
          </div>
          {/* Timing bar */}
          {t.total_sec != null && t.total_sec > 0 && (
            <div className="mt-2">
              <div className="flex gap-0.5 h-2 rounded-full overflow-hidden bg-[var(--chat-surface)]">
                {t.merge_sec != null && (
                  <div
                    className="bg-cyan-500"
                    style={{ width: `${(t.merge_sec / t.total_sec) * 100}%` }}
                    title="LoRA Merge"
                  />
                )}
                {t.convert_sec != null && (
                  <div
                    className="bg-violet-500"
                    style={{ width: `${(t.convert_sec / t.total_sec) * 100}%` }}
                    title="Convert"
                  />
                )}
                {t.ollama_import_sec != null && (
                  <div
                    className="bg-emerald-500"
                    style={{
                      width: `${(t.ollama_import_sec / t.total_sec) * 100}%`,
                    }}
                    title="Ollama Import"
                  />
                )}
              </div>
              <div className="flex gap-3 mt-1 text-[10px] text-[var(--chat-muted)]">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-cyan-500" /> Merge
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-violet-500" />{" "}
                  Convert
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />{" "}
                  Import
                </span>
              </div>
            </div>
          )}
        </Section>
      )}

      {/* Ollama */}
      {report.ollama.model_name && (
        <Section
          icon={<Server size={14} className="text-emerald-500" />}
          title="Ollama Model"
        >
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Stat label="Model Name" value={report.ollama.model_name} />
            <Stat
              label="Verified"
              value={
                report.ollama.verified ? (
                  <span className="flex items-center gap-1 text-emerald-400">
                    <CheckCircle2 size={12} /> Yes
                  </span>
                ) : (
                  <span className="text-amber-400">Unverified</span>
                )
              }
            />
            <Stat
              label="Import Method"
              value={
                report.method === "gguf"
                  ? "GGUF (Q4_K_M)"
                  : report.method === "safetensors_direct"
                  ? "Safetensors Direct"
                  : report.method ?? "—"
              }
            />
          </div>
        </Section>
      )}

      {/* Model Version */}
      {report.model_version && (
        <Section
          icon={<Package size={14} className="text-violet-500" />}
          title="Model Version"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Version" value={report.model_version.version_tag} />
            <Stat label="Status" value={report.model_version.status} />
            <Stat
              label="Ollama Name"
              value={report.model_version.ollama_model_name ?? "—"}
            />
            <Stat
              label="Invocations"
              value={report.model_version.total_invocations}
            />
          </div>
        </Section>
      )}
    </div>
  );
}
