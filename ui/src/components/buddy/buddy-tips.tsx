"use client";

import { useEffect, useCallback } from "react";
import { useBuddyStore } from "@/lib/stores/buddy-store";

/**
 * Speech-bubble overlay that displays contextual tips.
 * Fetches from the backend on mount and when explicitly refreshed.
 * Dismisses after 15 seconds or on click.
 */
export function BuddyTips() {
  const { currentTip, tipDismissedAt, name, setTip, dismissTip } = useBuddyStore();
  const AUTO_DISMISS_MS = 15_000;

  const fetchTip = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/buddy/tip?context=general");
      if (!res.ok) return;
      const data = await res.json();
      if (data.tip) setTip(data.tip);
    } catch {
      // backend unreachable — silent
    }
  }, [setTip]);

  /* Fetch a tip on mount if none showing and last was dismissed >60s ago */
  useEffect(() => {
    const now = Date.now();
    const cooldown = tipDismissedAt ? now - tipDismissedAt > 60_000 : true;
    if (!currentTip && cooldown) {
      fetchTip();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* Auto-dismiss timer */
  useEffect(() => {
    if (!currentTip) return;
    const timer = setTimeout(dismissTip, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [currentTip, dismissTip]);

  if (!currentTip) return null;

  return (
    <div className="buddy-tip-bubble" onClick={dismissTip} title="Click to dismiss">
      <span className="buddy-tip-name">{name}:</span>{" "}
      <span className="buddy-tip-text">{currentTip}</span>
      <style jsx>{`
        .buddy-tip-bubble {
          position: relative;
          background: var(--vscode-editorWidget-background, #1e1e2e);
          border: 1px solid var(--vscode-editorWidget-border, #313244);
          border-radius: 8px;
          padding: 8px 12px;
          font-size: 12px;
          line-height: 1.4;
          color: var(--vscode-editor-foreground, #cdd6f4);
          cursor: pointer;
          max-width: 260px;
          animation: tipFadeIn 0.25s ease-out;
        }
        .buddy-tip-bubble::after {
          content: "";
          position: absolute;
          bottom: -6px;
          left: 20px;
          width: 10px;
          height: 10px;
          background: var(--vscode-editorWidget-background, #1e1e2e);
          border-right: 1px solid var(--vscode-editorWidget-border, #313244);
          border-bottom: 1px solid var(--vscode-editorWidget-border, #313244);
          transform: rotate(45deg);
        }
        .buddy-tip-name {
          font-weight: 600;
          color: var(--vscode-textLink-foreground, #89b4fa);
        }
        @keyframes tipFadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
