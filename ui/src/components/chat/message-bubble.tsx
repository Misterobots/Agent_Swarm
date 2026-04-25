"use client";

import { useState, useMemo } from "react";
import type { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { cn } from "@/lib/utils/cn";
import { Bot, User, Palette, ChevronDown, ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";
import Link from "next/link";
import { ToolCallBlock } from "./tool-call-block";
import { ToolApprovalCard } from "./tool-approval-card";
import { MessageActions } from "./message-actions";

interface VerificationBadge {
  passed: boolean;
  score: number;
  iterations: number;
  correctorUsed: boolean;
}

interface MessageBubbleProps {
  message: ChatMessage;
  userPrompt?: string;
  isStreaming?: boolean;
  onEditMessage?: (content: string) => void;
  onRetryMessage?: () => void;
  onBranchMessage?: () => void;
  onApprove?: (callId: string, toolName: string, scope: "once" | "session" | "workspace") => void;
  onDeny?: (callId: string) => void;
}

function isCreativeRedirect(content: string): boolean {
  return content.includes("Creative Request Detected") || content.includes("Switch to the **Art Studio**");
}

export function MessageBubble({ message, userPrompt, isStreaming, onEditMessage, onRetryMessage, onBranchMessage, onApprove, onDeny }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showArtButton = !isUser && message.content && isCreativeRedirect(message.content);
  const [traceOpen, setTraceOpen] = useState(false);
  const artStudioHref = userPrompt
    ? `/art-studio?prompt=${encodeURIComponent(userPrompt)}`
    : "/art-studio";

  // Extract MarsRL verification info from thought trace
  const verification = useMemo((): VerificationBadge | null => {
    const thoughts = message.thoughtTrace;
    if (!thoughts || thoughts.length === 0) return null;

    let passed = false;
    let score = 0;
    let iterations = 0;
    let correctorUsed = false;
    let hasVerifier = false;

    for (const t of thoughts) {
      const c = t.content;
      // Match "→ Verifier: PASS (score: 0.85)" or "→ Verifier: FAIL (score: 0.40)"
      const match = c.match(/Verifier:\s*(PASS|FAIL)\s*\(score:\s*([\d.]+)\)/i);
      if (match) {
        hasVerifier = true;
        iterations++;
        passed = match[1].toUpperCase() === "PASS";
        score = parseFloat(match[2]);
      }
      if (/Corrector engaged/i.test(c) || /Correcting response/i.test(c)) {
        correctorUsed = true;
      }
    }
    if (!hasVerifier) return null;
    return { passed, score, iterations, correctorUsed };
  }, [message.thoughtTrace]);

  return (
    <div className={cn("group relative flex gap-3 py-4 px-4 msg-enter", isUser ? "bg-transparent" : "bg-[var(--chat-surface)]")}>
      <MessageActions
        content={message.content}
        isUser={isUser}
        onEdit={isUser && onEditMessage ? () => onEditMessage(message.content) : undefined}
        onRetry={isUser && onRetryMessage ? onRetryMessage : undefined}
        onBranch={onBranchMessage}
      />
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
          isUser
            ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_16%,transparent)] text-[var(--chat-accent-strong)] border border-[var(--chat-border)]"
            : "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_14%,transparent)] text-[var(--chat-accent-2)] border border-[var(--chat-border)]"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className="flex-1 min-w-0 text-[var(--chat-text)]">
        {verification && !isUser && (
          <div
            className={cn(
              "mb-2 inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-medium",
              verification.passed
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-amber-500/30 bg-amber-500/10 text-amber-400"
            )}
            title={`MarsRL Verification: ${verification.passed ? "Passed" : "Failed"} (score: ${verification.score.toFixed(2)}, ${verification.iterations} round${verification.iterations > 1 ? "s" : ""}${verification.correctorUsed ? ", corrector used" : ""})`}
          >
            {verification.passed ? (
              <ShieldCheck size={12} />
            ) : verification.score >= 0.4 ? (
              <ShieldAlert size={12} />
            ) : (
              <ShieldX size={12} />
            )}
            <span>Verified {verification.score.toFixed(2)}</span>
            {verification.correctorUsed && <span className="opacity-60">• corrected</span>}
          </div>
        )}
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : message.content ? (
          <>
            <MarkdownRenderer content={message.content} isStreaming={isStreaming} />
            {showArtButton && (
              <Link
                href={artStudioHref}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--chat-accent-2)] hover:brightness-110 text-white text-sm font-medium transition-colors"
              >
                <Palette size={16} />
                Open Art Studio
              </Link>
            )}
            {(!!message.thoughtTrace?.length || message.turnMetadata) && (
              <div className="mt-3 border border-[var(--chat-border)] rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setTraceOpen((v) => !v)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-[var(--chat-text)] bg-[var(--chat-panel)] hover:bg-[var(--chat-soft)]"
                >
                  <span>Agent Trace{message.thoughtTrace?.length ? ` (${message.thoughtTrace.length})` : ""}</span>
                  <ChevronDown
                    size={14}
                    className={cn("transition-transform", traceOpen ? "rotate-180" : "")}
                  />
                </button>
                {traceOpen && (
                  <div className="px-3 py-2 bg-[var(--chat-soft)]">
                    {message.turnMetadata && (
                      <div className="mb-2 flex items-center gap-2 flex-wrap">
                        <div className="inline-flex items-center gap-2 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)] px-2 py-1 text-[10px] uppercase tracking-wider text-[var(--chat-muted)]">
                          <span>Turn {message.turnMetadata.turnId.slice(0, 8)}</span>
                          {message.turnMetadata.agentName ? <span>{message.turnMetadata.agentName}</span> : null}
                        </div>
                        {message.turnMetadata.traceId && (
                          <a
                            href={`${window.location.protocol}//${window.location.hostname}:3000/project/default/traces/${message.turnMetadata.traceId}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-md border border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/10 px-2 py-1 text-[10px] font-medium text-[var(--chat-accent)] hover:bg-[var(--chat-accent)]/20 transition-colors"
                          >
                            🔗 View Trace
                          </a>
                        )}
                      </div>
                    )}
                    {message.thoughtTrace?.map((t, idx) => (
                      <p key={`${t.timestamp}-${idx}`} className="text-xs text-[var(--chat-accent-strong)] font-mono py-0.5">
                        [{new Date(t.timestamp).toLocaleTimeString()}] {t.content}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
            {!!message.toolCalls?.length && (
              <ToolCallBlock
                toolCalls={message.toolCalls}
                toolLifecycle={message.toolLifecycle}
                toolResults={message.toolResults}
              />
            )}
            {!!message.pendingApprovals?.length && onApprove && onDeny && (
              <div className="space-y-2">
                {message.pendingApprovals.map((approval) => (
                  <ToolApprovalCard
                    key={approval.tool_call_id}
                    approval={approval}
                    onApprove={onApprove}
                    onDeny={onDeny}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <span className="inline-block w-2 h-4 bg-[var(--chat-accent)] animate-pulse rounded-sm streaming-caret" />
        )}
      </div>
    </div>
  );
}
