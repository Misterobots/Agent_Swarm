"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import type { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { cn } from "@/lib/utils/cn";
import { Bot, User, Palette, ChevronDown, ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";
import Link from "next/link";
import { ToolCallBlock } from "./tool-call-block";
import { ToolApprovalCard } from "./tool-approval-card";
import { ClarificationCard } from "./clarification-card";
import { DesignArtifactCard } from "./design-artifact-card";
import { WorkshopQuestionsCard } from "./workshop-questions-card";
import { WorkflowActionsCard } from "./workflow-actions-card";
import { ModelQueueCard } from "./model-queue-card";
import { MessageActions } from "./message-actions";
import { MediaPreview } from "./media-preview";
import { ResponseSuggestionChips } from "./response-suggestion-chips";
import { FlagForm, FlaggedFollowupCard } from "./flagged-followup-card";
import { AgentTraceCard } from "./agent-trace-card";
import { useSettingsStore } from "@/lib/stores/settings-store";

// ---------------------------------------------------------------------------
// Swarm response parser — splits coordinator output into collapsible phases
// ---------------------------------------------------------------------------

const SWARM_MARKER = "**📋 Task Plan:";
const SUMMARY_MARKER = "---\n**📊 Coordination Summary";
const FOLLOWUP_MARKER = "\n---\n**💡 What would you like to do next?**";

const PHASE_SPLITS: { marker: string; title: string }[] = [
  { marker: "**📋 Task Plan:", title: "📋 Task Plan" },
  { marker: "**🔬 Research Phase", title: "🔬 Research & Planning" },
  { marker: "**🔨 Implementation Phase", title: "🔨 Implementation" },
  { marker: "**🧠 Synthesis Complete", title: "🧠 Synthesis" },
  { marker: "**🔍 Verification", title: "🔍 Verification" },
  { marker: "---\n**📊 Coordination Summary", title: "📊 Coordination Summary" },
];

interface SwarmParsed {
  processBlocks: { title: string; content: string }[];
  synthesisContent: string;
  followupContent: string;
}

function parseSwarmContent(content: string): SwarmParsed | null {
  if (!content.includes(SWARM_MARKER)) return null;

  // The synthesis is everything from the end of the coordination summary to the follow-up
  const summaryStart = content.indexOf(SUMMARY_MARKER);
  if (summaryStart === -1) return null; // Still streaming process phases

  // End of summary block: look for double-newline after summary
  const afterSummary = content.indexOf("\n\n", summaryStart + SUMMARY_MARKER.length);
  if (afterSummary === -1) return null;

  const processRaw = content.substring(0, afterSummary).trim();
  const remainder = content.substring(afterSummary).trim();

  // Split follow-up section if present
  const followupIdx = remainder.indexOf(FOLLOWUP_MARKER);
  const synthesisContent = followupIdx !== -1
    ? remainder.substring(0, followupIdx).trim()
    : remainder;
  const followupContent = followupIdx !== -1
    ? remainder.substring(followupIdx).trim()
    : "";

  // Split process text into labelled phase blocks
  const processBlocks: { title: string; content: string }[] = [];
  let remaining = processRaw;

  // Find all phase marker positions
  const positions: { idx: number; title: string; marker: string }[] = [];
  for (const { marker, title } of PHASE_SPLITS) {
    const idx = remaining.indexOf(marker);
    if (idx !== -1) positions.push({ idx, title, marker });
  }
  positions.sort((a, b) => a.idx - b.idx);

  for (let i = 0; i < positions.length; i++) {
    const start = positions[i].idx;
    const end = i + 1 < positions.length ? positions[i + 1].idx : remaining.length;
    const blockContent = remaining.substring(start, end).trim();
    if (blockContent) {
      processBlocks.push({ title: positions[i].title, content: blockContent });
    }
  }

  return { processBlocks, synthesisContent, followupContent };
}

// ---------------------------------------------------------------------------
// SwarmResponseRenderer — renders parsed swarm output with collapsible phases
// ---------------------------------------------------------------------------

function SwarmResponseRenderer({
  content,
  isStreaming,
}: {
  content: string;
  isStreaming?: boolean;
}) {
  const parsed = useMemo(() => (!isStreaming ? parseSwarmContent(content) : null), [content, isStreaming]);
  // Must be declared before any early returns — Rules of Hooks require unconditional hook calls
  const [processExpanded, setProcessExpanded] = useState(false);

  if (!parsed) {
    // Streaming or not yet fully parsed — render flat
    return <MarkdownRenderer content={content} isStreaming={isStreaming} />;
  }

  return (
    <div>
      {/* Main synthesis plan — shown first and prominently */}
      {parsed.synthesisContent && (
        <MarkdownRenderer content={parsed.synthesisContent} />
      )}

      {/* Follow-up suggestions */}
      {parsed.followupContent && (
        <div className="mt-3">
          <MarkdownRenderer content={parsed.followupContent} />
        </div>
      )}

      {/* Collapsible process phases - parent collapse wrapper */}
      {parsed.processBlocks.length > 0 && (
        <div className="mt-4 border border-[var(--chat-border)] rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setProcessExpanded((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-2 bg-[var(--chat-panel)] hover:bg-[var(--chat-soft)] text-[var(--chat-text)] transition-colors text-[13px] font-medium"
          >
            <span>Planning & Coordination Details</span>
            <ChevronDown size={14} className={cn("transition-transform duration-150", processExpanded && "rotate-180")} />
          </button>
          {processExpanded && (
            <div className="p-2 bg-[var(--chat-soft)] border-t border-[var(--chat-border)] space-y-1">
              {parsed.processBlocks.map((block) => (
                <CollapsiblePhase key={block.title} title={block.title} content={block.content} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CollapsiblePhase({ title, content }: { title: string; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-[var(--chat-border)] overflow-hidden text-[12px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-1.5 bg-[var(--chat-panel)] hover:bg-[var(--chat-soft)] text-[var(--chat-muted)] transition-colors"
      >
        <span className="font-medium">{title}</span>
        <ChevronDown size={12} className={cn("transition-transform duration-150", open && "rotate-180")} />
      </button>
      {open && (
        <div className="px-3 py-2 bg-[var(--chat-soft)] border-t border-[var(--chat-border)]">
          <MarkdownRenderer content={content} />
        </div>
      )}
    </div>
  );
}

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
  isLatest?: boolean;
  onEditMessage?: (content: string) => void;
  onRetryMessage?: () => void;
  onBranchMessage?: () => void;
  onApprove?: (callId: string, toolName: string, scope: "once" | "session" | "workspace") => void;
  onDeny?: (callId: string) => void;
  onSelectClarification?: (value: string) => void;
  /** Called when the user clicks an end-of-response suggestion chip or submits free text */
  onSelectFollowup?: (value: string) => void;
  onUseAlternativeModel?: (modelName: string) => void;
  /**
   * Called when the user submits a flag form on an assistant message.
   * Receives the user-edited title and optional tldr.
   */
  onFlag?: (messageId: string, title: string, tldr: string) => void | Promise<void>;
}

const COLLAPSE_THRESHOLD = 1200;

function isCreativeRedirect(content: string): boolean {
  return content.includes("Creative Request Detected") || content.includes("Switch to the **Art Studio**");
}

/** Strip markdown tokens and return a clean first line suitable as a title. */
function extractFlagTitle(content: string): string {
  const clean = content
    .replace(/```[\s\S]*?```/g, "")         // fenced code blocks
    .replace(/`[^`]+`/g, "")                // inline code
    .replace(/\*\*(.+?)\*\*/g, "$1")        // bold
    .replace(/\*(.+?)\*/g, "$1")            // italic
    .replace(/#{1,6}\s+/g, "")              // headings
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.length > 8) ?? content.trim();

  if (clean.length <= 55) return clean;
  return clean.slice(0, 52) + "…";
}

export function MessageBubble({ message, userPrompt, isStreaming, isLatest, onEditMessage, onRetryMessage, onBranchMessage, onApprove, onDeny, onSelectClarification, onSelectFollowup, onUseAlternativeModel, onFlag }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showArtButton = !isUser && message.content && isCreativeRedirect(message.content);
  const [traceOpen, setTraceOpen] = useState(false);
  const agentTransparency = useSettingsStore((s) => s.agentTransparency);

  // Flag-for-follow-up inline form state
  const [flagFormOpen, setFlagFormOpen] = useState(false);

  // Collapsible body
  const canCollapse = !isUser && message.content.length > COLLAPSE_THRESHOLD;
  const [isCollapsed, setIsCollapsed] = useState(false);
  const prevIsLatestRef = useRef(isLatest);
  useEffect(() => {
    // Auto-collapse when this message transitions from latest → previous
    if (prevIsLatestRef.current && !isLatest && canCollapse) {
      setIsCollapsed(true);
    }
    prevIsLatestRef.current = isLatest;
  }, [isLatest, canCollapse]);

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
    <>
    {/* Turn metadata row — visible above AI messages when agent/turn info is available */}
    {!isUser && message.turnMetadata && (message.turnMetadata.agentName || message.turnMetadata.streamModes?.length > 0) && (
      <div className="turn-meta-row flex items-center gap-1.5 px-4 md:px-6 pt-3 pb-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-accent)] opacity-70 select-none">
        <span className="text-[var(--chat-subtle)]">Turn</span>
        <span>{message.turnMetadata.turnId.slice(0, 8).toUpperCase()}</span>
        {message.turnMetadata.agentName && (
          <>
            <span className="text-[var(--chat-border)]">|</span>
            <span>{message.turnMetadata.agentName.toUpperCase()}</span>
          </>
        )}
        {message.turnMetadata.streamModes?.length > 0 && (
          <>
            <span className="text-[var(--chat-border)]">|</span>
            <span className="text-[var(--chat-muted)]">
              {message.turnMetadata.streamModes
                .map((m) => m.replace(/-/g, " ").toUpperCase())
                .join(" → ")}
            </span>
          </>
        )}
      </div>
    )}
    <div
      className={cn(
        "group relative flex gap-4 py-5 md:py-6 px-4 md:px-6 msg-enter",
        isUser
          ? "bg-transparent"
          : "bg-[color:color-mix(in_srgb,var(--chat-surface)_60%,transparent)]"
      )}
    >
      <MessageActions
        content={message.content}
        isUser={isUser}
        onEdit={isUser && onEditMessage ? () => onEditMessage(message.content) : undefined}
        onRetry={isUser && onRetryMessage ? onRetryMessage : undefined}
        onBranch={onBranchMessage}
        onFlagClick={!isUser && onFlag && !message.flaggedFollowup ? () => setFlagFormOpen(true) : undefined}
        flagged={!!message.flaggedFollowup}
      />
      <div
        className={cn(
          "flex-shrink-0 w-9 h-9 rounded-md flex items-center justify-center",
          isUser
            ? "text-[var(--chat-text)]"
            : "text-[var(--chat-accent)]"
        )}
        style={{
          background: isUser
            ? "var(--chat-panel)"
            : "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 4%, transparent))",
          border: isUser
            ? "1px solid var(--chat-border)"
            : "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
          boxShadow: "var(--elev-1), inset 0 1px 0 rgba(255,255,255,0.04)",
        }}
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
          <p className="whitespace-pre-wrap text-[14px] leading-[1.65] text-[var(--chat-text)]">{message.content}</p>
        ) : message.content ? (
          <>
            {/* Collapsible response body */}
            <div className="relative">
              <div className={cn(isCollapsed && "max-h-[320px] overflow-hidden")}>
                {message.content.includes(SWARM_MARKER) ? (
                  <SwarmResponseRenderer content={message.content} isStreaming={isStreaming} />
                ) : (
                  <MarkdownRenderer content={message.content} isStreaming={isStreaming} />
                )}
              </div>
              {isCollapsed && (
                <div
                  className="absolute bottom-0 left-0 right-0 h-12 pointer-events-none"
                  style={{ background: "linear-gradient(to top, color-mix(in srgb, var(--chat-surface) 90%, transparent), transparent)" }}
                />
              )}
            </div>
            {canCollapse && !isStreaming && (
              <button
                type="button"
                onClick={() => setIsCollapsed((v) => !v)}
                className="mt-1 mb-0.5 flex items-center gap-1 text-[11px] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
              >
                <ChevronDown size={11} className={cn("transition-transform duration-200", !isCollapsed && "rotate-180")} />
                {isCollapsed ? "Show full response" : "Collapse"}
              </button>
            )}
            {showArtButton && (
              <Link
                href={artStudioHref}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--chat-accent-2)] hover:brightness-110 text-white text-sm font-medium transition-colors"
              >
                <Palette size={16} />
                Open Art Studio
              </Link>
            )}
            {/* Media Attachments (Images, Videos, 3D Models) */}
            {message.mediaAttachments && message.mediaAttachments.length > 0 && (
              <div className="mt-2 space-y-2">
                {message.mediaAttachments.map((media) => (
                  <MediaPreview key={media.id} media={media} />
                ))}
              </div>
            )}
            {/* Structured agent trace (new) — coordinator / worker / verifier stream */}
            {!!message.agentTrace?.length && (
              <AgentTraceCard
                events={message.agentTrace}
                isStreaming={isStreaming}
                transparency={agentTransparency}
              />
            )}
            {/* Legacy thought trace — shown when no structured agentTrace but thoughtTrace exists */}
            {!message.agentTrace?.length && (!!message.thoughtTrace?.length || message.turnMetadata) && (
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
                        <div className="inline-flex items-center gap-2 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)] px-2 py-1 text-[10px] tracking-wide text-[var(--chat-muted)]">
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
        {/* ClarificationCard — rendered outside content conditional so it shows even when content is empty */}
        {message.pendingClarification && onSelectClarification && (
          <ClarificationCard
            card={message.pendingClarification}
            onSelect={onSelectClarification}
            disabled={isStreaming}
          />
        )}
        {/* Model queue status — rendered outside content conditional so it shows even when content is empty */}
        {message.pendingQueueStatus && (
          <ModelQueueCard
            status={message.pendingQueueStatus}
            onUseAlternative={onUseAlternativeModel}
          />
        )}
        {/* Design artifact — rendered outside content conditional so it shows even when content is empty */}
        {message.designArtifact && (
          <DesignArtifactCard
            artifact={message.designArtifact}
            onSend={onSelectFollowup}
          />
        )}
        {/* Workshop Phase-1 loading skeleton — shown while questions generate */}
        {message.workshopQuestionsLoading && !message.workshopQuestions?.length && (
          <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-950/10 overflow-hidden animate-pulse">
            <div className="px-3 py-2 border-b border-amber-500/20 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-amber-500/30" />
              <div className="h-3 w-36 rounded bg-amber-500/20" />
            </div>
            <div className="p-3 space-y-2">
              {[62, 48, 70, 54, 66, 44, 58].map((w, i) => (
                <div key={i} className="flex items-center gap-2 px-2 py-1.5 rounded-md border border-amber-500/10">
                  <div className="h-2.5 w-3 rounded bg-amber-500/15 shrink-0" />
                  <div className={`h-2.5 rounded bg-amber-500/15`} style={{ width: `${w}%` }} />
                </div>
              ))}
            </div>
          </div>
        )}
        {/* Workshop Phase-1 question accordion — inline answer inputs */}
        {message.workshopQuestions && message.workshopQuestions.length > 0 && (
          <WorkshopQuestionsCard
            questions={message.workshopQuestions}
            onSend={onSelectFollowup}
          />
        )}
        {/* Workshop Phase-2 pipeline continuation buttons */}
        {message.workflowNextSteps && message.workflowNextSteps.length > 0 && (
          <WorkflowActionsCard
            steps={message.workflowNextSteps}
            onSend={onSelectFollowup}
          />
        )}
        {/* File-change activity chips — inline signals from swarm worker file writes */}
        {!isUser && message.fileChanges && message.fileChanges.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.fileChanges.map((fc, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
                style={{
                  background: "var(--chat-surface)",
                  border: "1px solid var(--chat-border)",
                  color: "var(--chat-muted)",
                }}
                title={fc.path}
              >
                <span>{fc.op === "created" ? "📄" : fc.op === "deleted" ? "🗑️" : "✏️"}</span>
                <span>{fc.path.split("/").pop()}</span>
                {fc.size != null && (
                  <span style={{ opacity: 0.5 }}>
                    {fc.size < 1024 ? `${fc.size}B` : `${(fc.size / 1024).toFixed(1)}K`}
                  </span>
                )}
              </span>
            ))}
          </div>
        )}
        {/* Fallback: brief finished but buttons weren't parsed — give manual escape hatch */}
        {!isUser && !isStreaming && isLatest &&
         (!message.workflowNextSteps || message.workflowNextSteps.length === 0) &&
         message.content?.includes("Design Mode Prompt") &&
         message.content?.includes("Swarm Mode") &&
         onSelectFollowup && (
          <div
            className="mt-2 px-3 py-2 rounded-md text-[11px] flex flex-wrap items-center gap-x-2 gap-y-1"
            style={{ background: "var(--chat-surface)", border: "1px solid var(--chat-border)", color: "var(--chat-muted)" }}
          >
            <span>Continue manually:</span>
            <button
              className="underline hover:opacity-80 transition-opacity"
              style={{ color: "var(--chat-accent-strong)" }}
              onClick={() => onSelectFollowup("/design")}
            >
              /design
            </button>
            <span>or</span>
            <button
              className="underline hover:opacity-80 transition-opacity"
              style={{ color: "var(--chat-accent-strong)" }}
              onClick={() => onSelectFollowup("/swarm")}
            >
              /swarm
            </button>
          </div>
        )}
        {/* End-of-response follow-up chips — only on the latest assistant message, after streaming */}
        {!isUser
          && !isStreaming
          && isLatest
          && message.suggestedFollowups
          && message.suggestedFollowups.length > 0
          && onSelectFollowup && (
            <ResponseSuggestionChips
              followups={message.suggestedFollowups}
              onSelect={onSelectFollowup}
              disabled={isStreaming}
            />
          )}
        {/* Flag for follow-up: inline form opens when flag button is clicked */}
        {!isUser && flagFormOpen && !message.flaggedFollowup && (
          <FlagForm
            defaultTitle={extractFlagTitle(message.content)}
            onSubmit={async (title, tldr) => {
              setFlagFormOpen(false);
              await onFlag?.(message.id, title, tldr);
            }}
            onCancel={() => setFlagFormOpen(false)}
          />
        )}
        {/* Flagged follow-up confirmation card */}
        {!isUser && message.flaggedFollowup && (
          <FlaggedFollowupCard followup={message.flaggedFollowup} />
        )}
      </div>
    </div>
    </>
  );
}
