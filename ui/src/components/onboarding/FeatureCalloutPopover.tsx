"use client";

/**
 * Spotlight card for a feature callout. Rendered by FeatureCalloutBadge when the
 * feature's popover is the active one; positioned above its anchor (the toolbar
 * sits near the bottom of the screen) with a downward arrow.
 *
 * Presentational + self-managed dismissal: outside-click (mousedown) and Escape
 * both call onDismiss. "Try it" is shown only when the feature has a tryItPrompt.
 */

import { useEffect, useRef } from "react";
import type { FeatureMeta } from "@/lib/onboarding/feature-registry";

export function FeatureCalloutPopover({
  meta,
  onTryIt,
  onDismiss,
}: {
  meta: FeatureMeta;
  onTryIt?: () => void;
  onDismiss: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const Icon = meta.icon;

  useEffect(() => {
    const onDocDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onDismiss();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    document.addEventListener("mousedown", onDocDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [onDismiss]);

  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={meta.title}
      className="absolute bottom-full left-0 mb-2.5 z-50 w-64 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-elevated)] p-3 text-left"
      style={{ boxShadow: "var(--elev-2)" }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-accent)]">
          New
        </span>
        <Icon size={13} className="text-[var(--chat-accent)]" />
        <span className="text-sm font-semibold text-[var(--chat-text)]">{meta.title}</span>
      </div>
      <p className="text-xs text-[var(--chat-muted)] leading-snug mb-2.5">{meta.description}</p>
      <div className="flex items-center gap-2">
        {onTryIt && (
          <button
            type="button"
            onClick={onTryIt}
            className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-[var(--chat-accent)] text-[var(--chat-on-accent,#fff)] hover:opacity-90 transition-opacity"
          >
            Try it
          </button>
        )}
        <button
          type="button"
          onClick={onDismiss}
          className="text-[11px] font-medium px-2.5 py-1 rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
        >
          Got it
        </button>
      </div>
      {/* downward arrow pointing at the anchor */}
      <span
        aria-hidden
        className="absolute top-full left-5 -mt-1 h-2 w-2 rotate-45 border-b border-r border-[var(--chat-border)] bg-[var(--chat-elevated)]"
      />
    </div>
  );
}
