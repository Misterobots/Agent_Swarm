"use client";

import { useState, useCallback } from "react";
import { History, ChevronDown, ChevronUp } from "lucide-react";
import { usePalaceStore } from "@/lib/stores/palace-store";

export function AuditBadge({ memoryId }: { memoryId: string }) {
  const auditLog = usePalaceStore((s) => s.auditLog);
  const auditLoading = usePalaceStore((s) => s.auditLoading);
  const loadAuditLog = usePalaceStore((s) => s.loadAuditLog);

  const [expanded, setExpanded] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const handleToggle = useCallback(() => {
    if (!loaded) {
      loadAuditLog(memoryId);
      setLoaded(true);
    }
    setExpanded(!expanded);
  }, [loaded, expanded, loadAuditLog, memoryId]);

  return (
    <div>
      <button
        onClick={handleToggle}
        className="flex items-center gap-1.5 text-xs transition-colors"
        style={{ color: "var(--chat-muted)" }}
      >
        <History size={12} />
        <span>Change history</span>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {expanded && (
        <div
          className="mt-2 rounded-lg overflow-hidden"
          style={{
            background: "var(--chat-panel)",
            border: "1px solid var(--chat-border)",
          }}
        >
          {auditLoading && (
            <div className="p-3 text-xs" style={{ color: "var(--chat-muted)" }}>
              Loading history…
            </div>
          )}

          {!auditLoading && auditLog.length === 0 && (
            <div className="p-3 text-xs" style={{ color: "var(--chat-muted)" }}>
              No changes recorded.
            </div>
          )}

          {!auditLoading &&
            auditLog.map((entry) => (
              <div
                key={entry.id}
                className="px-3 py-2 text-xs"
                style={{ borderBottom: "1px solid var(--chat-border)" }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span>
                    <span
                      className="font-medium"
                      style={{
                        color:
                          entry.action === "deleted"
                            ? "var(--chat-accent-2)"
                            : entry.action === "created"
                            ? "var(--chat-accent)"
                            : "var(--chat-text)",
                      }}
                    >
                      {entry.action}
                    </span>{" "}
                    <span style={{ color: "var(--chat-muted)" }}>
                      by {entry.actor_id} ({entry.actor_role})
                    </span>
                  </span>
                  <span style={{ color: "var(--chat-muted)", fontSize: "10px" }}>
                    {new Date(entry.created_at).toLocaleString()}
                  </span>
                </div>

                {/* Diff for edits */}
                {entry.action === "edited" && entry.previous_content && entry.new_content && (
                  <div className="mt-1 space-y-1">
                    <div
                      className="px-2 py-1 rounded text-xs leading-relaxed"
                      style={{
                        background: "rgba(239,68,68,0.1)",
                        color: "var(--chat-accent-2)",
                        textDecoration: "line-through",
                      }}
                    >
                      {entry.previous_content.slice(0, 100)}
                      {entry.previous_content.length > 100 ? "…" : ""}
                    </div>
                    <div
                      className="px-2 py-1 rounded text-xs leading-relaxed"
                      style={{
                        background: "rgba(34,197,94,0.1)",
                        color: "var(--chat-accent)",
                      }}
                    >
                      {entry.new_content.slice(0, 100)}
                      {entry.new_content.length > 100 ? "…" : ""}
                    </div>
                  </div>
                )}

                {/* Changed fields summary */}
                {entry.changed_fields &&
                  Object.keys(entry.changed_fields).length > 0 &&
                  entry.action !== "edited" && (
                    <div className="mt-1" style={{ color: "var(--chat-muted)" }}>
                      Changed: {Object.keys(entry.changed_fields).join(", ")}
                    </div>
                  )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
