"use client";

import { useState } from "react";
import type { FileChange } from "@/types/chat";

const OP_LABEL: Record<string, string> = {
  created:  "created",
  modified: "modified",
  deleted:  "deleted",
};

const OP_COLOR: Record<string, string> = {
  created:  "text-green-400 border-green-700/50",
  modified: "text-[var(--chat-accent)] border-[var(--chat-accent)]/30",
  deleted:  "text-red-400 border-red-700/50",
};

function DiffLine({ line, num }: { line: string; num: number }) {
  const isAdd    = line.startsWith("+") && !line.startsWith("+++");
  const isDel    = line.startsWith("-") && !line.startsWith("---");
  const isHunk   = line.startsWith("@@");
  const isMeta   = line.startsWith("---") || line.startsWith("+++");

  const bg =
    isAdd  ? "bg-green-950/40" :
    isDel  ? "bg-red-950/40"   :
    isHunk ? "bg-[var(--chat-surface)]" :
    isMeta ? "bg-[var(--chat-surface)] opacity-60" :
    "";

  const textColor =
    isAdd  ? "text-green-300" :
    isDel  ? "text-red-300"   :
    isHunk ? "text-[var(--chat-accent)] font-medium" :
    isMeta ? "text-[var(--chat-muted)]" :
    "text-[var(--chat-text)]";

  return (
    <div className={`flex min-w-0 ${bg}`}>
      {/* Gutter */}
      <span className="select-none flex-shrink-0 w-10 text-right pr-2 text-[var(--chat-muted)] opacity-50 text-[10px] leading-[1.6] font-mono">
        {!isHunk && !isMeta && num}
      </span>
      {/* Sign */}
      <span className={`flex-shrink-0 w-4 text-center font-mono text-[11px] leading-[1.6] ${textColor}`}>
        {isAdd ? "+" : isDel ? "−" : isHunk ? "" : " "}
      </span>
      {/* Content */}
      <span className={`flex-1 min-w-0 font-mono text-[11px] leading-[1.6] whitespace-pre break-all ${textColor}`}>
        {/* Strip the leading +/-/space */}
        {isAdd || isDel ? line.slice(1) : line}
      </span>
    </div>
  );
}

interface DiffViewerProps {
  fileChange: FileChange;
}

export function DiffViewer({ fileChange }: DiffViewerProps) {
  const [open, setOpen] = useState(false);
  const filename = fileChange.path.split(/[/\\]/).pop() ?? fileChange.path;
  const opColor  = OP_COLOR[fileChange.op] ?? OP_COLOR.modified;

  const lines = fileChange.diff?.split("\n") ?? [];
  let lineNum = 0;
  const numberedLines = lines.map((line) => {
    if (!line.startsWith("-") && !line.startsWith("@@") &&
        !line.startsWith("---") && !line.startsWith("+++")) {
      lineNum++;
    }
    return { line, num: lineNum };
  });

  const stats = lines.reduce(
    (acc, l) => {
      if (l.startsWith("+") && !l.startsWith("+++")) acc.added++;
      if (l.startsWith("-") && !l.startsWith("---")) acc.removed++;
      return acc;
    },
    { added: 0, removed: 0 }
  );

  return (
    <div className={`rounded-md overflow-hidden border ${opColor.split(" ")[1]} text-xs`}
         style={{ background: "var(--chat-bg)" }}>
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-[var(--chat-surface)] transition-colors"
        style={{ background: "var(--chat-surface)" }}
      >
        <span className="flex-shrink-0 text-[var(--chat-muted)]">
          {open ? "▾" : "▸"}
        </span>
        <span className="font-mono text-[var(--chat-text)] truncate">{filename}</span>
        <span className={`text-[10px] uppercase tracking-wider flex-shrink-0 ${opColor.split(" ")[0]}`}>
          {OP_LABEL[fileChange.op]}
        </span>
        {fileChange.diff && (
          <span className="ml-auto flex items-center gap-2 flex-shrink-0 text-[10px] font-mono">
            {stats.added   > 0 && <span className="text-green-400">+{stats.added}</span>}
            {stats.removed > 0 && <span className="text-red-400">−{stats.removed}</span>}
          </span>
        )}
      </button>

      {/* Diff body */}
      {open && fileChange.diff && (
        <div className="overflow-x-auto border-t border-[var(--chat-border)]">
          <div className="min-w-0">
            {numberedLines.map(({ line, num }, i) => (
              <DiffLine key={i} line={line} num={num} />
            ))}
          </div>
        </div>
      )}

      {/* No diff available (write_file) */}
      {open && !fileChange.diff && (
        <div className="px-4 py-2 text-[var(--chat-muted)] text-[11px] border-t border-[var(--chat-border)]">
          File {OP_LABEL[fileChange.op]} — no diff available
          {fileChange.size != null && ` (${(fileChange.size / 1024).toFixed(1)} KB)`}
        </div>
      )}
    </div>
  );
}
