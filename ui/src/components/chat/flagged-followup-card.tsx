"use client";

/**
 * FlaggedFollowupCard — confirmation chip rendered below an assistant message
 * once the user has flagged it for follow-up.
 *
 * FlagForm — the inline form that collects title + optional tldr before
 * the flag is submitted.
 *
 * Styling mirrors ClarificationCard: var(--chat-*) tokens, rounded-md borders.
 */

import { useState } from "react";
import { Bookmark, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { FlaggedFollowup } from "@/types/chat";

// ---------------------------------------------------------------------------
// FlaggedFollowupCard — shown after a flag is confirmed
// ---------------------------------------------------------------------------

interface FlaggedFollowupCardProps {
  followup: FlaggedFollowup;
}

export function FlaggedFollowupCard({ followup }: FlaggedFollowupCardProps) {
  const time = new Date(followup.flaggedAt).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={cn(
        "mt-3 flex items-start gap-2.5 rounded-md border overflow-hidden",
        "border-[color:color-mix(in_srgb,var(--chat-accent)_35%,var(--chat-border))]",
        "bg-[color:color-mix(in_srgb,var(--chat-accent)_6%,var(--chat-bg))]"
      )}
    >
      {/* Left accent strip */}
      <div className="w-0.5 self-stretch bg-[var(--chat-accent)] flex-shrink-0 opacity-70" />

      <div className="flex-1 min-w-0 py-2.5 pr-3">
        {/* Header row */}
        <div className="flex items-center gap-1.5 mb-1">
          <Bookmark
            size={11}
            className="text-[var(--chat-accent)] flex-shrink-0"
            fill="currentColor"
          />
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-accent)]">
            Flagged for Follow-up
          </span>
          <CheckCircle2
            size={10}
            className="text-[var(--chat-accent)] opacity-60 flex-shrink-0"
          />
          <span className="ml-auto text-[9px] text-[var(--chat-muted)] opacity-50 tabular-nums">
            {time}
          </span>
        </div>

        {/* Title */}
        <p className="text-[13px] font-medium text-[var(--chat-text)] leading-snug">
          {followup.title}
        </p>

        {/* Tldr */}
        {followup.tldr && (
          <p className="mt-0.5 text-[11px] text-[var(--chat-muted)] leading-relaxed">
            {followup.tldr}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FlagForm — inline form for capturing title + tldr
// ---------------------------------------------------------------------------

interface FlagFormProps {
  /** Pre-populated title derived from message content. */
  defaultTitle: string;
  /** Called when the user submits the form. */
  onSubmit: (title: string, tldr: string) => void | Promise<void>;
  /** Called when the user cancels. */
  onCancel: () => void;
}

export function FlagForm({ defaultTitle, onSubmit, onCancel }: FlagFormProps) {
  const [title, setTitle] = useState(defaultTitle);
  const [tldr, setTldr] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = title.trim();
    if (!t || submitting) return;
    setSubmitting(true);
    try {
      await onSubmit(t, tldr.trim());
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        "mt-3 rounded-md border overflow-hidden",
        "border-[color:color-mix(in_srgb,var(--chat-accent)_35%,var(--chat-border))]"
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "flex items-center gap-1.5 px-3 py-2 border-b",
          "border-[color:color-mix(in_srgb,var(--chat-accent)_25%,var(--chat-border))]",
          "bg-[color:color-mix(in_srgb,var(--chat-accent)_8%,var(--chat-panel))]"
        )}
      >
        <Bookmark size={11} className="text-[var(--chat-accent)] flex-shrink-0" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--chat-accent)]">
          Flag for Follow-up
        </span>
      </div>

      <div className="p-3 space-y-2.5 bg-[var(--chat-bg)]">
        {/* Title field */}
        <div>
          <label className="block text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--chat-muted)] mb-1">
            Title <span className="text-[var(--chat-accent)] font-normal normal-case tracking-normal">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value.slice(0, 60))}
            placeholder="Short imperative phrase…"
            maxLength={60}
            required
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            className={cn(
              "w-full rounded-md border px-2.5 py-1.5 text-xs",
              "border-[var(--chat-border)] bg-[var(--chat-panel)]",
              "text-[var(--chat-text)] placeholder-[var(--chat-muted)]",
              "focus:outline-none focus:border-[var(--chat-accent)] transition-colors"
            )}
          />
          <p className="mt-0.5 text-right text-[9px] text-[var(--chat-muted)] opacity-50 tabular-nums">
            {title.length}/60
          </p>
        </div>

        {/* Tldr field */}
        <div>
          <label className="block text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--chat-muted)] mb-1">
            Summary{" "}
            <span className="font-normal normal-case tracking-normal opacity-50">(optional)</span>
          </label>
          <textarea
            value={tldr}
            onChange={(e) => setTldr(e.target.value)}
            placeholder="1–2 sentences describing the follow-up work…"
            rows={2}
            className={cn(
              "w-full rounded-md border px-2.5 py-1.5 text-xs resize-none",
              "border-[var(--chat-border)] bg-[var(--chat-panel)]",
              "text-[var(--chat-text)] placeholder-[var(--chat-muted)]",
              "focus:outline-none focus:border-[var(--chat-accent)] transition-colors"
            )}
          />
        </div>

        {/* Action row */}
        <div className="flex items-center justify-end gap-2 pt-0.5">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="px-3 py-1.5 text-xs rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim() || submitting}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors",
              "border-[color:color-mix(in_srgb,var(--chat-accent)_50%,var(--chat-border))]",
              "bg-[color:color-mix(in_srgb,var(--chat-accent)_12%,transparent)]",
              "text-[var(--chat-accent)]",
              "hover:border-[var(--chat-accent)] hover:bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)]",
              "disabled:opacity-40 disabled:cursor-default"
            )}
          >
            <Bookmark size={11} />
            {submitting ? "Flagging…" : "Flag it"}
          </button>
        </div>
      </div>
    </form>
  );
}
