"use client";

import { useState } from "react";
import type { Artifact, ToolCallEvent, ToolLifecycleEvent, ToolResult } from "@/types/chat";

interface ToolCallBlockProps {
  toolCalls: ToolCallEvent[];
  toolLifecycle?: ToolLifecycleEvent[];
  toolResults?: ToolResult[];
  onArtifactAction?: (artifact: Artifact, action: "apply" | "reject" | "open") => void;
}

function getStateBadge(state?: string) {
  const badges: Record<string, { icon: string; label: string; color: string }> = {
    completed: { icon: "âœ“", label: "Done", color: "text-green-500" },
    executing: { icon: "...", label: "Running", color: "text-yellow-500" },
    queued: { icon: "o", label: "Queued", color: "text-blue-500" },
    error: { icon: "!", label: "Error", color: "text-red-500" },
    cancelled: { icon: "x", label: "Cancelled", color: "text-[var(--chat-muted)]" },
  };
  return badges[state || "queued"] || badges.queued;
}

function getToolState(toolId: string, lifecycle?: ToolLifecycleEvent[]): ToolLifecycleEvent | undefined {
  if (!lifecycle || !toolId) return undefined;
  return lifecycle.filter((e) => e.tool_call_id === toolId).at(-1);
}

function getToolResult(toolId: string, results?: ToolResult[]): ToolResult | undefined {
  if (!results || !toolId) return undefined;
  return results.find((r) => r.tool_call_id === toolId);
}

export function ToolCallBlock({ toolCalls, toolLifecycle, toolResults, onArtifactAction }: ToolCallBlockProps) {
  const [artifactState, setArtifactState] = useState<Record<string, "applied" | "rejected" | undefined>>({});
  if (!toolCalls.length) return null;

  function handleArtifactAction(artifact: Artifact, action: "apply" | "reject" | "open") {
    if (action === "apply") {
      setArtifactState((prev) => ({ ...prev, [artifact.id]: "applied" }));
    } else if (action === "reject") {
      setArtifactState((prev) => ({ ...prev, [artifact.id]: "rejected" }));
    }

    if (action === "open") {
      const previewContent = artifact.content.slice(0, 1200);
      if (typeof window !== "undefined") {
        window.alert(previewContent || "No artifact content available.");
      }
    }

    onArtifactAction?.(artifact, action);
  }

  return (
    <div className="mt-3 rounded-md border border-[var(--chat-border)] bg-[var(--chat-bg)] overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--chat-border)] text-xs uppercase tracking-wider text-[var(--chat-muted)]">
        Tool Calls ({toolCalls.length})
      </div>
      <div className="divide-y divide-[var(--chat-border)]">
        {toolCalls.map((t, idx) => {
          const stateEvent = getToolState(t.tool_call_id || "", toolLifecycle);
          const result = getToolResult(t.tool_call_id || "", toolResults);
          const derivedState = stateEvent?.state || (result?.success ? "completed" : undefined);
          const badge = getStateBadge(derivedState);

          return (
            <div key={`${t.tool_call_id || t.timestamp}-${idx}`} className="px-3 py-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs font-semibold text-[var(--chat-text)] truncate">{t.tool_name}</span>
                  <span className={`flex items-center gap-1 text-xs font-medium ${badge.color}`}>
                    {badge.icon} {badge.label}
                  </span>
                </div>
                <span className="text-[10px] text-[var(--chat-subtle)]">{new Date(t.timestamp).toLocaleTimeString()}</span>
              </div>

              {typeof stateEvent?.progress === "number" && (
                <div className="w-full h-1.5 rounded bg-[var(--chat-surface)] overflow-hidden">
                  <div
                    className="h-full bg-[var(--chat-accent-2)]"
                    style={{ width: `${Math.max(0, Math.min(100, stateEvent.progress))}%` }}
                  />
                </div>
              )}

              {result?.output ? (
                <div className="text-xs text-[var(--chat-text)] max-h-40 overflow-y-auto bg-[var(--chat-soft)] p-1.5 rounded whitespace-pre-wrap">
                  {result.output}
                </div>
              ) : t.content ? (
                <p className="text-xs text-[var(--chat-text)]">{t.content}</p>
              ) : null}

              {result?.artifacts?.length ? (
                <div className="space-y-2">
                  <div className="text-xs text-[var(--chat-subtle)] font-mono">Artifacts: {result.artifacts.length}</div>
                  {result.artifacts.map((artifact) => {
                    const state = artifactState[artifact.id];
                    return (
                      <div
                        key={artifact.id}
                        className="rounded border border-[var(--chat-border)] bg-[var(--chat-soft)] p-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] text-[var(--chat-text)] truncate">
                            {artifact.type}{artifact.language ? ` (${artifact.language})` : ""}
                          </span>
                          {state ? (
                            <span className={`text-[10px] uppercase tracking-wider ${state === "applied" ? "text-green-400" : "text-red-400"}`}>
                              {state}
                            </span>
                          ) : null}
                        </div>
                        {artifact.description ? (
                          <p className="mt-1 text-[11px] text-[#a7968c]">{artifact.description}</p>
                        ) : null}
                        <div className="mt-2 flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleArtifactAction(artifact, "apply")}
                            className="px-2 py-1 text-[10px] rounded border border-green-700 text-green-300 hover:bg-green-900/30"
                          >
                            Apply
                          </button>
                          <button
                            type="button"
                            onClick={() => handleArtifactAction(artifact, "reject")}
                            className="px-2 py-1 text-[10px] rounded border border-red-700 text-red-300 hover:bg-red-900/30"
                          >
                            Reject
                          </button>
                          <button
                            type="button"
                            onClick={() => handleArtifactAction(artifact, "open")}
                            className="px-2 py-1 text-[10px] rounded border border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                          >
                            Open
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}

              {t.tool_input ? (
                <pre className="text-xs text-[var(--chat-muted)] overflow-x-auto whitespace-pre-wrap bg-[var(--chat-soft)] p-1.5 rounded">
                  {JSON.stringify(t.tool_input, null, 2)}
                </pre>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
