"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { useChatStore } from "@/lib/stores/chat-store";
import { useDevStore } from "@/lib/stores/dev-store";
import { MessageBubble } from "./message-bubble";
import { ThinkingIndicator } from "./thinking-indicator";
import { BuddyComment } from "@/components/buddy/buddy-comment";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { InputToolbar } from "./input-toolbar";
import { SwarmDrawer } from "@/components/swarm/swarm-drawer";
import { useSwarmStore } from "@/lib/stores/swarm-store";
import { useSwarmBroadcast } from "@/lib/hooks/use-swarm-broadcast";
import { AwaySummaryBanner, useAwaySummary } from "./away-summary";
import { Bot, Sparkles, Code2, Search, Lightbulb, X } from "lucide-react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils/cn";
import { ChatStatusBar } from "./chat-status-bar";
import { ChatPreviewPane } from "./chat-preview-pane";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { THEME_PERSONALITIES } from "@/lib/themes/personalities";
import { useBuddyStore } from "@/lib/stores/buddy-store";
import { useConversationSync } from "@/lib/hooks/use-conversation-sync";
import { useAutoGoal } from "@/lib/hooks/use-goals";
import { GoalsPanel } from "@/components/goals/GoalsPanel";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import type { FileAttachment } from "@/types/chat";

function usageBarClass(pct: number): string {
  if (pct >= 0.95) return "bg-red-500";
  if (pct >= 0.85) return "bg-orange-500";
  if (pct >= 0.7) return "bg-amber-500";
  return "bg-[var(--chat-muted)]";
}

export function ChatView({ showDevContext = false }: { showDevContext?: boolean }) {
  const selectedText = useDevStore((s) => s.selectedText);
  const editorLanguage = useDevStore((s) => s.editorLanguage);
  const activeFile = useDevStore((s) => s.activeFile);
  const agentEnabled = useDevStore((s) => s.agentEnabled);
  const editorSyncEnabled = useDevStore((s) => s.editorSyncEnabled);
  const setEditorContent = useDevStore((s) => s.setEditorContent);
  const setActiveFile = useDevStore((s) => s.setActiveFile);
  const clearSelectedText = useDevStore((s) => s.setSelectedText);
  const showChatPreview = useDevStore((s) => s.showChatPreview);

  // Editor sync: called when AI writes a file
  const handleToolResult = useCallback(
    (toolName: string, toolInput: Record<string, unknown>, _output: string) => {
      if (!editorSyncEnabled) return;
      if (toolName !== "write_file") return;
      const writtenPath = (toolInput.path as string) || "";
      const writtenContent = (toolInput.content as string) || "";
      if (!writtenPath) return;
      if (activeFile && writtenPath !== activeFile && !activeFile.endsWith(writtenPath)) return;
      setEditorContent(writtenContent);
      if (!activeFile) setActiveFile(writtenPath);
    },
    [editorSyncEnabled, activeFile, setEditorContent, setActiveFile]
  );

  // Load conversations from server on mount for cross-device sync
  useConversationSync();
  useAutoGoal();

  const devMode = showDevContext && agentEnabled;

  const { messages, isStreaming, statusMessage, latestThought, streamMode, tokenUsage, sendMessage, compactConversation, stopGeneration } = useChatStream({
    devMode,
    onToolResult: devMode ? handleToolResult : undefined,
  });
  const { activeConversationId, activeConversation, updateConversation } = useChatStore();
  const model = useSettingsStore((s) => s.model);
  const theme = useSettingsStore((s) => s.theme);
  const personality = THEME_PERSONALITIES[theme] ?? THEME_PERSONALITIES.memex;
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeConv = activeConversation();
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const { isMobile } = useIsMobile();
  const buddyReact = useBuddyStore((s) => s.react);
  const buddyStage = useBuddyStore((s) => s.evolutionStage);
  const buddySetComment = useBuddyStore((s) => s.setComment);
  const buddyMuted = useBuddyStore((s) => s.muted);
  const { awayEvents, pushEvent, dismiss: dismissAway } = useAwaySummary();

  // Swarm state — used for showThinking extension + recall FAB
  useSwarmBroadcast();
  const swarmActive = useSwarmStore((s) => s.active);
  const swarmDismissed = useSwarmStore((s) => s.dismissed);
  const setSwarmDismissed = useSwarmStore((s) => s.setDismissed);
  const theaterPhase = useSwarmStore((s) => s.theaterPhase);
  const swarmWorkers = useSwarmStore((s) => s.workers);

  // Show the thinking indicator when streaming and either we have a status
  // message or the assistant message is still empty (waiting for first content)
  const lastMsg = messages[messages.length - 1];
  const showThinking =
    (isStreaming && (statusMessage !== null || (lastMsg?.role === "assistant" && !lastMsg.content))) ||
    (swarmActive && theaterPhase !== "complete" && theaterPhase !== "idle");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, lastMsg?.content, statusMessage]);

  // Buddy reactions on stream events
  const prevStreamingRef = useRef(false);
  useEffect(() => {
    if (isStreaming && !prevStreamingRef.current) {
      buddyReact("message_sent");
      pushEvent("message", "Message sent to agents");
    }
    if (!isStreaming && prevStreamingRef.current) {
      buddyReact("response_received");
      pushEvent("message", "Response received");
      // Fetch a contextual buddy comment from backend (stage 2+ only)
      if (buddyStage >= 2 && !buddyMuted) {
        fetch("/api/backend/v1/buddy/comment?context=response_received")
          .then((r) => r.ok ? r.json() : null)
          .then((data) => { if (data?.comment) buddySetComment(data.comment); })
          .catch(() => { /* non-fatal */ });
      }
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, buddyReact, pushEvent]);

  // Message action handlers
  const handleEditMessage = useCallback((content: string) => {
    sendMessage(content);
  }, [sendMessage]);

  const handleRetryMessage = useCallback((messageIndex: number) => {
    const msg = messages[messageIndex];
    if (msg?.role === "user") {
      sendMessage(msg.content);
    }
  }, [messages, sendMessage]);

  // Tool approval handlers (dev mode only)
  const handleApprove = useCallback(
    async (callId: string, toolName: string, scope: "once" | "session" | "workspace") => {
      const autoMap: Record<string, string> = { session: "session", workspace: "workspace", once: "none" };
      try {
        await fetch(`/api/backend/api/v1/dev/approve/${callId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auto: autoMap[scope], tool_name: toolName }),
        });
      } catch (e) {
        console.error("[ChatView] approve failed", e);
      }
    },
    []
  );

  const handleDeny = useCallback(async (callId: string) => {
    try {
      await fetch(`/api/backend/api/v1/dev/deny/${callId}`, { method: "POST" });
    } catch (e) {
      console.error("[ChatView] deny failed", e);
    }
  }, []);

  return (
    <>
    <div className="chat-shell flex h-full overflow-hidden" data-route="chat">
      <div className="flex-1 min-w-0 flex flex-col relative overflow-hidden">
      {/* Header */}
      <div
        className="relative flex items-center gap-3 bg-[var(--chat-surface)] px-3 md:px-5 py-2.5 min-w-0"
        style={{ paddingLeft: "calc(var(--sidebar-rail-pad, 0px) + 0.75rem)" }}
      >
        {/* Breadcrumb + title */}
        <div className="flex flex-col min-w-0 flex-1">
          <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--chat-muted)] select-none">
            <span>Chat</span>
            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-50 flex-shrink-0"><path d="M9 18l6-6-6-6"/></svg>
            <span>Active Session</span>
          </div>
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-semibold text-[var(--chat-text)] truncate leading-tight">
              {activeConv?.title || "New Conversation"}
            </span>
          </div>
        </div>

        {/* Model selector — compact */}
        <div className="flex-shrink-0 hidden md:block">
          <ModelSelector />
        </div>

        {/* Right: Swarm status + token bar */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Swarm Online dot */}
          <div className="hidden md:flex items-center gap-1.5 text-[11px] text-[var(--chat-accent)]">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--chat-accent)] flex-shrink-0" style={{ animation: "pulse-dot 2.5s ease-in-out infinite" }} />
            <span className="font-medium">Swarm Online</span>
          </div>

          {/* Token usage bar */}
          <button
            type="button"
            onClick={() => { void compactConversation(); }}
            className="group flex items-center gap-2 rounded-full px-2.5 py-1 transition-colors hover:bg-[var(--hover-tint)]"
            title={`Context: ${(tokenUsage.pct * 100).toFixed(1)}% (${tokenUsage.used.toLocaleString()}/${tokenUsage.total.toLocaleString()}) — click to compact`}
          >
            <div
              className="w-16 md:w-24 h-1.5 rounded-full overflow-hidden bg-[var(--chat-panel)] border border-[var(--chat-border)]"
              style={{ boxShadow: "inset 0 1px 2px rgba(0,0,0,0.15)" }}
            >
              <div
                className={cn("h-full transition-all duration-500 ease-out", usageBarClass(tokenUsage.pct))}
                style={{
                  width: `${Math.min(100, tokenUsage.pct * 100)}%`,
                  boxShadow: tokenUsage.pct > 0.7 ? "0 0 8px currentColor" : "none",
                }}
              />
            </div>
            <span className="text-[11px] font-medium text-[var(--chat-muted)] group-hover:text-[var(--chat-text)] transition-colors hidden md:inline tabular-nums min-w-[2.5rem] text-right">
              {(tokenUsage.pct * 100).toFixed(0)}%
            </span>
          </button>
        </div>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin">
        {tokenUsage.pct >= 0.95 && (
          <div className="mx-auto max-w-3xl mt-3 px-3 md:px-4">
            <div className="rounded-md border border-[color:color-mix(in_srgb,var(--chat-accent-2)_50%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent-2)_10%,transparent)] px-3 py-2 text-xs text-[var(--chat-text)]">
              Context is near capacity. Compact now to preserve response quality.
            </div>
          </div>
        )}
        <AwaySummaryBanner events={awayEvents} onDismiss={dismissAway} />
        {messages.length === 0 ? (
          <EmptyChatState
            greeting={personality.greeting}
            subtitle={personality.subtitle}
            onPrompt={(prompt) => {
              window.dispatchEvent(new CustomEvent("chat:prefill", { detail: prompt }));
            }}
          />
        ) : (
          <div className="max-w-3xl mx-auto px-3 md:px-0">
            {messages.map((msg, idx) => {
              // Don't render an empty assistant placeholder while ThinkingIndicator is visible —
              // it would show a lone blinking cursor on its own row.
              if (showThinking && idx === messages.length - 1 && msg.role === "assistant" && !msg.content) {
                return null;
              }
              // Find the preceding user message for creative-redirect links
              let precedingUserPrompt: string | undefined;
              if (msg.role === "assistant") {
                for (let i = idx - 1; i >= 0; i--) {
                  if (messages[i].role === "user") {
                    precedingUserPrompt = messages[i].content;
                    break;
                  }
                }
              }
              return (
                <div key={msg.id}>
                  {msg.turnMetadata && (
                    <div className="mx-4 mt-2 text-[10px] uppercase tracking-wider text-[var(--chat-muted)]">
                      Turn {msg.turnMetadata.turnId.slice(0, 8)}
                      {msg.turnMetadata.agentName ? ` | ${msg.turnMetadata.agentName}` : ""}
                      {msg.turnMetadata.streamModes?.length ? ` | ${msg.turnMetadata.streamModes.join(" -> ")}` : ""}
                    </div>
                  )}
                  <MessageBubble
                    message={msg}
                    userPrompt={precedingUserPrompt}
                    isStreaming={isStreaming && idx === messages.length - 1 && msg.role === "assistant"}
                    isLatest={idx === messages.length - 1}
                    onEditMessage={handleEditMessage}
                    onRetryMessage={() => handleRetryMessage(idx)}
                    onApprove={devMode ? handleApprove : undefined}
                    onDeny={devMode ? handleDeny : undefined}
                    onSelectClarification={(val) => sendMessage(val)}
                  />
                </div>
              );
            })}
            {showThinking && (
              <ThinkingIndicator
                statusMessage={statusMessage}
                latestThought={latestThought}
                streamMode={streamMode}
                swarmPhase={theaterPhase}
              />
            )}
            {/* Buddy inline comment — appears after last message */}
            {!showThinking && <BuddyComment />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Toolbar */}
      <InputToolbar
        attachments={attachments}
        onAttachmentsChange={setAttachments}
        disabled={isStreaming}
      />

      {/* Code context chip (dev workspace only) */}
      {showDevContext && selectedText && (
        <div className="mx-4 mb-1 flex items-start gap-2 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs">
          <Code2 size={12} className="mt-0.5 shrink-0 text-[var(--chat-accent)]" />
          <span className="flex-1 truncate text-[var(--chat-muted)]">
            Selected: <span className="text-[var(--chat-text)] font-mono">{selectedText.slice(0, 80)}{selectedText.length > 80 ? "…" : ""}</span>
          </span>
          <button
            onClick={() => clearSelectedText("")}
            className="shrink-0 text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            title="Clear selection context"
          >
            <X size={11} />
          </button>
        </div>
      )}

      {/* Input */}
      <ChatInput
        onSend={(msg) => {
          const context = showDevContext && selectedText
            ? `\`\`\`${editorLanguage}\n${selectedText}\n\`\`\`\n\n${msg}`
            : msg;
          sendMessage(context, attachments);
          setAttachments([]);
        }}
        onStop={stopGeneration}
        isStreaming={isStreaming}
      />
      <ChatStatusBar
        model={activeConv?.model || model}
        tokenPct={tokenUsage.pct * 100}
        isStreaming={isStreaming}
        latestThought={latestThought}
      />
      {/* Recall FAB — visible on all screen sizes when swarm is dismissed and active */}
      {swarmActive && swarmDismissed && theaterPhase !== "idle" && (
        <button
          type="button"
          onClick={() => setSwarmDismissed(false)}
          className="fixed bottom-[calc(3.5rem+env(safe-area-inset-bottom)+8px)] right-4 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full bg-[var(--chat-surface)] border border-[var(--chat-border)] text-sm font-semibold text-[var(--chat-text)] hover:text-[var(--chat-accent-strong)] active:scale-95 transition-all"
          style={{ boxShadow: "var(--elev-2)" }}
          aria-label="Recall swarm panel"
        >
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${theaterPhase === "complete" ? "bg-emerald-400" : "bg-emerald-400 animate-pulse"}`} />
          Swarm &middot; {swarmWorkers.length} pioneer{swarmWorkers.length !== 1 ? "s" : ""}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7"/>
          </svg>
        </button>
      )}
      </div>{/* end chat column */}
      {/* Preview pane — slides in as a sibling column when a build deploys a web app */}
      {showChatPreview && <ChatPreviewPane />}
      {/* Goals panel — sibling column, sits between chat and swarm */}
      <GoalsPanel />
      {/* Swarm theater drawer — sibling column, squeezes chat */}
      <SwarmDrawer />
    </div>
  </>
  );
}

const STARTER_PROMPTS: Array<{ icon: React.ComponentType<{ size?: number; className?: string }>; label: string; prompt: string }> = [
  { icon: Code2,     label: "Write code",       prompt: "Help me write a small Python script that " },
  { icon: Search,    label: "Look something up", prompt: "Search the web for " },
  { icon: Lightbulb, label: "Brainstorm",       prompt: "Brainstorm ideas for " },
  { icon: Sparkles,  label: "Summarize",        prompt: "Summarize this for me: " },
];

function EmptyChatState({
  greeting,
  subtitle,
  onPrompt,
}: {
  greeting: string;
  subtitle: string;
  onPrompt: (prompt: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-12">
      <div className="w-full max-w-xl flex flex-col items-center text-center">
        <div className="relative mb-6">
          <div
            className="w-20 h-20 rounded-2xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 6%, transparent))",
              border: "1px solid color-mix(in srgb, var(--chat-accent) 30%, var(--chat-border))",
              boxShadow: "var(--elev-2), inset 0 1px 0 rgba(255,255,255,0.06)",
            }}
          >
            <Bot size={36} className="text-[var(--chat-accent)]" />
          </div>
          <div
            className="absolute -inset-4 -z-10 rounded-3xl opacity-60 blur-2xl"
            style={{ background: "radial-gradient(circle, var(--chat-accent-soft), transparent 70%)" }}
          />
        </div>
        <h1 className="text-2xl font-semibold text-[var(--chat-text)] tracking-tight mb-2">
          {greeting}
        </h1>
        <p className="text-[15px] text-[var(--chat-muted)] mb-8">{subtitle}</p>

        <div className="w-full grid grid-cols-2 gap-2.5">
          {STARTER_PROMPTS.map(({ icon: Icon, label, prompt }) => (
            <Card
              key={label}
              as="div"
              role="button"
              tabIndex={0}
              padding="none"
              interactive
              onClick={() => onPrompt(prompt)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPrompt(prompt);
                }
              }}
              className="group flex items-center gap-3 px-4 py-3 text-left"
            >
              <div className="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] group-hover:border-[var(--chat-accent)] group-hover:text-[var(--chat-accent)] transition-colors text-[var(--chat-muted)]">
                <Icon size={15} />
              </div>
              <span className="text-sm font-medium text-[var(--chat-text)]">{label}</span>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}