"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Eye, X } from "lucide-react";

interface AwayEvent {
  type: "message" | "tool" | "error" | "compact";
  summary: string;
  timestamp: number;
}

interface AwaySummaryProps {
  /** Called when the user was away and events accumulated */
  onDismiss?: () => void;
}

export function useAwaySummary() {
  const [awayEvents, setAwayEvents] = useState<AwayEvent[]>([]);
  const [isAway, setIsAway] = useState(false);
  const awayRef = useRef(false);
  const eventsRef = useRef<AwayEvent[]>([]);

  useEffect(() => {
    const handleVisibility = () => {
      const away = document.hidden;
      awayRef.current = away;
      setIsAway(away);

      if (!away && eventsRef.current.length > 0) {
        // User came back — surface the accumulated events
        setAwayEvents([...eventsRef.current]);
        eventsRef.current = [];
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  const pushEvent = useCallback((type: AwayEvent["type"], summary: string) => {
    if (awayRef.current) {
      eventsRef.current.push({ type, summary, timestamp: Date.now() });
    }
  }, []);

  const dismiss = useCallback(() => {
    setAwayEvents([]);
  }, []);

  return { awayEvents, isAway, pushEvent, dismiss };
}

export function AwaySummaryBanner({
  events,
  onDismiss,
}: {
  events: AwayEvent[];
  onDismiss: () => void;
}) {
  if (events.length === 0) return null;

  const messageCount = events.filter((e) => e.type === "message").length;
  const toolCount = events.filter((e) => e.type === "tool").length;
  const errorCount = events.filter((e) => e.type === "error").length;

  const parts: string[] = [];
  if (messageCount > 0) parts.push(`${messageCount} message${messageCount > 1 ? "s" : ""}`);
  if (toolCount > 0) parts.push(`${toolCount} tool action${toolCount > 1 ? "s" : ""}`);
  if (errorCount > 0) parts.push(`${errorCount} error${errorCount > 1 ? "s" : ""}`);

  return (
    <div className="mx-auto max-w-5xl mt-3 px-4 away-banner-enter">
      <div className="flex items-center gap-3 rounded-md border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent)_8%,transparent)] px-3 py-2">
        <Eye size={14} className="text-[var(--chat-accent)] flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-[var(--chat-text)]">
            While you were away: {parts.join(", ")}
          </p>
          {events.length <= 5 && (
            <div className="mt-1 space-y-0.5">
              {events.map((e, i) => (
                <p key={`${e.timestamp}-${i}`} className="text-[10px] text-[var(--chat-muted)] truncate">
                  {e.summary}
                </p>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onDismiss}
          className="flex-shrink-0 p-1 text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
