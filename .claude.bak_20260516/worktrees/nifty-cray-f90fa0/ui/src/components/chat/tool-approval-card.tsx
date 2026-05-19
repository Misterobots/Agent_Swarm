"use client";

import { useState } from "react";
import type { ToolApprovalEvent } from "@/types/chat";

interface ToolApprovalCardProps {
  approval: ToolApprovalEvent;
  /** Called when the user approves. scope: "once" | "session" | "workspace" */
  onApprove: (callId: string, toolName: string, scope: "once" | "session" | "workspace") => void;
  /** Called when the user denies. */
  onDeny: (callId: string) => void;
}

const TOOL_ICONS: Record<string, string> = {
  read_file: "📄",
  write_file: "✏️",
  list_directory: "📁",
  run_command: "⚡",
};

const TOOL_LABELS: Record<string, string> = {
  read_file: "Read File",
  write_file: "Write File",
  list_directory: "List Directory",
  run_command: "Run Command",
};

function ArgPreview({ args }: { args?: Record<string, unknown> }) {
  if (!args || Object.keys(args).length === 0) return null;
  return (
    <div className="mt-1.5 rounded bg-[var(--chat-soft)] border border-[var(--chat-border)] px-2 py-1.5 space-y-0.5 text-xs font-mono text-[var(--chat-text)] overflow-x-auto max-h-28">
      {Object.entries(args).map(([k, v]) => (
        <div key={k} className="flex gap-2 items-start">
          <span className="text-[var(--chat-muted)] shrink-0">{k}:</span>
          <span className="text-[var(--chat-text)] whitespace-pre-wrap break-all">
            {typeof v === "string" && v.length > 200
              ? v.slice(0, 200) + "…"
              : JSON.stringify(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ToolApprovalCard({ approval, onApprove, onDeny }: ToolApprovalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICONS[approval.tool_name] ?? "🔧";
  const label = TOOL_LABELS[approval.tool_name] ?? approval.tool_name;

  return (
    <div className="mt-3 rounded-md border border-amber-700/50 bg-[var(--chat-bg)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 bg-amber-950/30 border-b border-amber-700/40">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base">{icon}</span>
          <span className="text-xs font-semibold text-amber-200 truncate">{label}</span>
          <span className="text-[10px] uppercase tracking-wider text-amber-500 border border-amber-700 rounded px-1">
            Pending
          </span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-[10px] text-amber-500 hover:text-amber-300 shrink-0"
          aria-label={expanded ? "Collapse arguments" : "Expand arguments"}
        >
          {expanded ? "hide args ▲" : "show args ▼"}
        </button>
      </div>

      {/* Args preview */}
      {expanded && (
        <div className="px-3 py-2 border-b border-amber-700/30">
          <ArgPreview args={approval.tool_input} />
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        {/* Primary: approve once */}
        <button
          type="button"
          onClick={() => onApprove(approval.tool_call_id, approval.tool_name, "once")}
          className="px-2.5 py-1 text-xs rounded border border-green-700 text-green-300 hover:bg-green-900/30 font-medium"
        >
          Approve
        </button>

        {/* Auto-approve options */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-[var(--chat-muted)]">Auto:</span>
          <button
            type="button"
            onClick={() => onApprove(approval.tool_call_id, approval.tool_name, "session")}
            className="px-2 py-1 text-[10px] rounded border border-[var(--chat-border)] text-[var(--chat-muted)] hover:border-green-700 hover:text-green-400"
            title="Auto-approve this tool for the rest of this session"
          >
            session
          </button>
          <button
            type="button"
            onClick={() => onApprove(approval.tool_call_id, approval.tool_name, "workspace")}
            className="px-2 py-1 text-[10px] rounded border border-[var(--chat-border)] text-[var(--chat-muted)] hover:border-green-700 hover:text-green-400"
            title="Auto-approve this tool for this workspace (persisted)"
          >
            workspace
          </button>
        </div>

        {/* Deny */}
        <button
          type="button"
          onClick={() => onDeny(approval.tool_call_id)}
          className="ml-auto px-2.5 py-1 text-xs rounded border border-red-700 text-red-400 hover:bg-red-900/30"
        >
          Deny
        </button>
      </div>
    </div>
  );
}
