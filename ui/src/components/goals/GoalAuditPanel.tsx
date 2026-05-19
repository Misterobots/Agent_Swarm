"use client";

/**
 * GoalAuditPanel — shows completion gate result.
 * Used before marking a goal complete to ensure evidence requirements are met.
 */

import { cn } from "@/lib/utils/cn";

interface Props {
  missing: string[];
  onConfirm?: () => void;
  onCancel?: () => void;
}

export function GoalAuditPanel({ missing, onConfirm, onCancel }: Props) {
  const passed = missing.length === 0;

  return (
    <div className={cn(
      "rounded-xl border p-4 flex flex-col gap-3",
      passed
        ? "bg-green-500/10 border-green-500/25"
        : "bg-red-500/10 border-red-500/25",
    )}>
      {/* Header */}
      <div className="flex items-center gap-2">
        {passed ? (
          <svg className="w-4 h-4 text-green-400 flex-shrink-0" fill="none" viewBox="0 0 16 16">
            <path d="M3 8l4 4 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ) : (
          <svg className="w-4 h-4 text-red-400 flex-shrink-0" fill="none" viewBox="0 0 16 16">
            <path d="M8 5v4M8 11v1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        )}
        <p className={cn("text-sm font-semibold", passed ? "text-green-400" : "text-red-400")}>
          {passed ? "Audit passed — goal can be completed." : "Audit blocked — missing evidence."}
        </p>
      </div>

      {/* Missing requirements */}
      {!passed && (
        <ul className="flex flex-col gap-1 pl-1">
          {missing.map((req) => (
            <li key={req} className="flex items-start gap-2 text-xs text-red-300">
              <span className="mt-0.5 w-3 h-3 flex-shrink-0">
                <svg fill="none" viewBox="0 0 12 12">
                  <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </span>
              {req}
            </li>
          ))}
        </ul>
      )}

      {/* Actions */}
      {passed && onConfirm && (
        <div className="flex gap-2 pt-1">
          {onCancel && (
            <button
              onClick={onCancel}
              className="flex-1 py-1.5 text-xs rounded-lg border border-[var(--border)] text-[var(--chat-subtle)] hover:text-[var(--chat-fg)] transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={onConfirm}
            className="flex-1 py-1.5 text-xs rounded-lg bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30 transition-colors font-medium"
          >
            Mark Complete ✓
          </button>
        </div>
      )}
    </div>
  );
}
