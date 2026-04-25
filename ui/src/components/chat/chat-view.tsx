"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { useChatStore } from "@/lib/stores/chat-store";
import { useDevStore } from "@/lib/stores/dev-store";
import { MessageBubble } from "./message-bubble";
import { ThinkingIndicator } from "./thinking-indicator";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { InputToolbar } from "./input-toolbar";
import { UltraplanToggle } from "./ultraplan-toggle";
import { UltrathinkToggle } from "./ultrathink-toggle";
import { WebGroundingToggle } from "./web-grounding-toggle";
import { DocGroundingToggle } from "./doc-grounding-toggle";
import { FileGroundingToggle } from "./file-grounding-toggle";
import { SwarmToggle } from "./swarm-toggle";
import { SwarmDrawer } from "@/components/swarm/swarm-drawer";
import { useSwarmStore } from "@/lib/stores/swarm-store";
import { useSwarmBroadcast } from "@/lib/hooks/use-swarm-broadcast";
import { AwaySummaryBanner, useAwaySummary } from "./away-summary";
import { Bot, Brain, Code2, X, MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { ChatStatusBar } from "./chat-status-bar";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { ThemeSelector } from "./theme-selector";
import { THEME_PERSONALITIES } from "@/lib/themes/personalities";
import { useBuddyStore } from "@/lib/stores/buddy-store";
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

  const devMode = showDevContext && agentEnabled;

  const { messages, isStreaming, statusMessage, latestThought, streamMode, tokenUsage, sendMessage, compactConversation, stopGeneration } = useChatStream({
    devMode,
    onToolResult: devMode ? handleToolResult : undefined,
  });
  const { activeConversationId, activeConversation, updateConversation } = useChatStore();
  const model = useSettingsStore((s) => s.model);
  const theme = useSettingsStore((s) => s.theme);
  const personality = THEME_PERSONALITIES[theme];
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeConv = activeConversation();
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const { isMobile } = useIsMobile();
  const buddyReact = useBuddyStore((s) => s.react);
  const { awayEvents, pushEvent, dismiss: dismissAway } = useAwaySummary();

  // Swarm state — used for showThinking extension + recall FAB
  useSwarmBroadcast();
  const swarmActive = useSwarmStore((s) => s.active);
  const swarmDismissed = useSwarmStore((s) => s.dismissed);
  const setSwarmDismissed = useSwarmStore((s) => s.setDismissed);
  const theaterPhase = useSwarmStore((s) => s.theaterPhase);
  const swarmWorkers = useSwarmStore((s) => s.workers);

  // Close mobile overflow menu on outside tap
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const handleTouch = (e: MouseEvent | TouchEvent) => {
      if (mobileMenuRef.current && !mobileMenuRef.current.contains(e.target as Node)) {
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleTouch);
    document.addEventListener("touchstart", handleTouch);
    return () => {
      document.removeEventListener("mousedown", handleTouch);
      document.removeEventListener("touchstart", handleTouch);
    };
  }, [mobileMenuOpen]);

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
    <div className="chat-shell flex h-full overflow-hidden" data-route="chat">
      <div className="flex-1 min-w-0 flex flex-col relative overflow-hidden">
      {/* Header */
      <div className="flex items-center justify-between border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-3 md:px-4 py-2 min-w-0">
        <div className="flex items-center gap-2 md:gap-3 min-w-0 flex-1">
          <ModelSelector />
          {!isMobile && <ThemeSelector />}
          {!isMobile && <UltraplanToggle />}
          {!isMobile && <UltrathinkToggle />}
          <SwarmToggle />
          {!isMobile && <WebGroundingToggle />}
          {!isMobile && <DocGroundingToggle />}
          {!isMobile && <FileGroundingToggle />}
          {!isMobile && activeConversationId && (
            <button
              type="button"
              onClick={() =>
                updateConversation(activeConversationId, {
                  memoryEnabled: !(activeConv?.memoryEnabled ?? false),
                })
              }
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
                activeConv?.memoryEnabled
                  ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
                  : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)]"
              )}
              title="Toggle cross-session memory recall"
            >
              <Brain size={14} />
              Memory
            </button>
          )}
          {/* Mobile overflow menu trigger */}
          {isMobile && (
            <div className="relative" ref={mobileMenuRef}>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-1.5 rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
              >
                <MoreHorizontal size={18} />
              </button>
              {mobileMenuOpen && (
                <div className="absolute top-full left-0 mt-1 z-30 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] shadow-lg p-2 space-y-1 min-w-[160px] max-h-[60vh] overflow-y-auto">
                  <div className="px-2 py-1.5"><UltraplanToggle /></div>
                  <div className="px-2 py-1.5"><UltrathinkToggle /></div>
                  <div className="px-2 py-1.5"><ThemeSelector /></div>
                  <div className="px-2 py-1.5"><WebGroundingToggle /></div>
                  <div className="px-2 py-1.5"><DocGroundingToggle /></div>
                  <div className="px-2 py-1.5"><FileGroundingToggle /></div>
                  {activeConversationId && (
                    <button
                      type="button"
                      onClick={() => {
                        updateConversation(activeConversationId, {
                          memoryEnabled: !(activeConv?.memoryEnabled ?? false),
                        });
                        setMobileMenuOpen(false);
                      }}
                      className={cn(
                        "w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs transition-colors",
                        activeConv?.memoryEnabled
                          ? "text-[var(--chat-accent-strong)]"
                          : "text-[var(--chat-muted)]"
                      )}
                    >
                      <Brain size={14} />
                      Memory {activeConv?.memoryEnabled ? "On" : "Off"}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
          <button
            type="button"
            onClick={() => {
              void compactConversation();
            }}
            className="w-16 md:w-44 h-2 rounded-full bg-[var(--chat-panel)] overflow-hidden border border-[var(--chat-border)]"
            title={`Context usage: ${(tokenUsage.pct * 100).toFixed(1)}% (${tokenUsage.used}/${tokenUsage.total}) - Click to compact`}
          >
            <div
              className={cn("h-full transition-all", usageBarClass(tokenUsage.pct))}
              style={{ width: `${Math.min(100, tokenUsage.pct * 100)}%` }}
            />
          </button>
          <span className="text-xs text-[var(--chat-muted)] hidden md:inline min-w-[3rem]">
            {(tokenUsage.pct * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {tokenUsage.pct >= 0.95 && (
          <div className="mx-auto max-w-3xl mt-3 px-3 md:px-4">
            <div className="rounded-md border border-[color:color-mix(in_srgb,var(--chat-accent-2)_50%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent-2)_10%,transparent)] px-3 py-2 text-xs text-[var(--chat-text)]">
              Context is near capacity. Compact now to preserve response quality.
            </div>
          </div>
        )}
        <AwaySummaryBanner events={awayEvents} onDismiss={dismissAway} />
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--chat-muted)] gap-4 px-4">
            <div className="w-16 h-16 rounded-2xl bg-[color:color-mix(in_srgb,var(--chat-accent)_14%,transparent)] flex items-center justify-center border border-[var(--chat-border)]">
              <Bot size={32} className="text-[var(--chat-accent-strong)]" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-medium text-[var(--chat-text)] mb-1">{personality.greeting}</h2>
              <p className="text-sm text-[var(--chat-muted)]">{personality.subtitle}</p>
            </div>
          </div>
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
      {/* Mobile recall FAB — visible when swarm is dismissed and active */}
      {isMobile && swarmActive && swarmDismissed && theaterPhase !== "idle" && theaterPhase !== "complete" && (
        <button
          type="button"
          onClick={() => setSwarmDismissed(false)}
          className="fixed bottom-[calc(3.5rem+env(safe-area-inset-bottom)+8px)] right-4 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full bg-[var(--chat-surface)] border border-white/10 shadow-lg text-sm font-semibold text-white/70 hover:text-white/90 active:scale-95 transition-all"
          aria-label="Recall swarm panel"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
          Swarm &middot; {swarmWorkers.length} pioneer{swarmWorkers.length !== 1 ? "s" : ""}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7"/>
          </svg>
        </button>
      )}
      </div>{/* end chat column */}
      {/* Swarm theater drawer — sibling column, squeezes chat */}
      <SwarmDrawer />
    </div>
  );
}
