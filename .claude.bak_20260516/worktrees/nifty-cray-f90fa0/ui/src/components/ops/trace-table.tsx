"use client";

import { cn } from "@/lib/utils/cn";
import type { Trace } from "@/types/ops";

interface TraceTableProps {
  traces: Trace[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function TraceTable({ traces, selectedId, onSelect }: TraceTableProps) {
  if (traces.length === 0) {
    return (
      <div className="text-center py-12 text-[var(--chat-muted)] text-sm">
        No traces found
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-[var(--chat-muted)] border-b border-[var(--chat-border)]">
            <th className="text-left px-4 py-2 font-medium">ID</th>
            <th className="text-left px-4 py-2 font-medium">Agent</th>
            <th className="text-left px-4 py-2 font-medium">Input</th>
            <th className="text-right px-4 py-2 font-medium">Latency</th>
            <th className="text-center px-4 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((t) => (
            <tr
              key={t.id}
              onClick={() => onSelect(t.id)}
              className={cn(
                "border-b border-[var(--chat-border)]/30 cursor-pointer transition-colors",
                t.id === selectedId
                  ? "bg-[var(--chat-accent)]/15"
                  : "hover:bg-[var(--chat-surface)]"
              )}
            >
              <td className="px-4 py-2 font-mono text-xs text-[var(--chat-muted)]">
                {t.id.slice(0, 8)}
              </td>
              <td className="px-4 py-2 text-[var(--chat-text)]">{t.name}</td>
              <td className="px-4 py-2 text-[var(--chat-muted)] truncate max-w-xs">
                {t.input_preview}
              </td>
              <td className="px-4 py-2 text-right text-[var(--chat-muted)]">
                {t.latency !== null ? `${t.latency.toFixed(2)}s` : "—"}
              </td>
              <td className="px-4 py-2 text-center">
                <span
                  className={cn(
                    "inline-block px-2 py-0.5 rounded text-xs font-medium",
                    t.level !== "ERROR"
                      ? "bg-emerald-900/30 text-emerald-400"
                      : "bg-red-900/30 text-red-400"
                  )}
                >
                  {t.level === "ERROR" ? "ERROR" : "SUCCESS"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
