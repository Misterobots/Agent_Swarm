"use client";

import { useEffect, useRef, useState } from "react";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { useChatStore } from "@/lib/stores/chat-store";
import { MessageBubble } from "./message-bubble";
import { ThinkingIndicator } from "./thinking-indicator";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { InputToolbar } from "./input-toolbar";
import { Bot, Brain } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { ChatStatusBar } from "./chat-status-bar";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { ThemeSelector } from "./theme-selector";
import { THEME_PERSONALITIES } from "@/lib/themes/personalities";
import type { FileAttachment } from "@/types/chat";

function usageBarClass(pct: number): string {
  if (pct >= 0.95) return "bg-red-500";
  if (pct >= 0.85) return "bg-orange-500";
  if (pct >= 0.7) return "bg-amber-500";
  return "bg-zinc-500";
}

export function ChatView() {
  const { messages, isStreaming, statusMessage, latestThought, pipelineSteps, streamPhase, tokenUsage, sendMessage, compactConversation, stopGeneration } = useChatStream();
  const { activeConversationId, activeConversation, updateConversation } = useChatStore();
  const model = useSettingsStore((s) => s.model);
  const theme = useSettingsStore((s) => s.theme);
  const personality = THEME_PERSONALITIES[theme];
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeConv = activeConversation();
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);

  const lastMsg = messages[messages.length - 1];
  // Show thinking indicator only during the thinking/pipeline phase.
  // Once content starts streaming (streamPhase === "responding"), collapse it.
  const showThinking = isStreaming && streamPhase === "thinking";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, lastMsg?.content, statusMessage]);

  return (
    <div className="chat-shell flex flex-col h-full" data-route="chat">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-2">
        <div className="flex items-center gap-3">
          <ModelSelector />
          <ThemeSelector />
          {activeConversationId && (
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
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              void compactConversation();
            }}
            className="w-44 h-2 rounded-full bg-[var(--chat-panel)] overflow-hidden border border-[var(--chat-border)]"
            title={`Context usage: ${(tokenUsage.pct * 100).toFixed(1)}% (${tokenUsage.used}/${tokenUsage.total}) - Click to compact`}
          >
            <div
              className={cn("h-full transition-all", usageBarClass(tokenUsage.pct))}
              style={{ width: `${Math.min(100, tokenUsage.pct * 100)}%` }}
            />
          </button>
          <span className="text-xs text-[var(--chat-muted)] min-w-[3rem]">
            {(tokenUsage.pct * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700">
        {tokenUsage.pct >= 0.95 && (
          <div className="mx-auto max-w-3xl mt-3 px-4">
            <div className="rounded-md border border-[color:color-mix(in_srgb,var(--chat-accent-2)_50%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent-2)_10%,transparent)] px-3 py-2 text-xs text-[var(--chat-text)]">
              Context is near capacity. Compact now to preserve response quality.
            </div>
          </div>
        )}
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--chat-muted)] gap-4">
            <div className="w-16 h-16 rounded-2xl bg-[color:color-mix(in_srgb,var(--chat-accent)_14%,transparent)] flex items-center justify-center border border-[var(--chat-border)]">
              <Bot size={32} className="text-[var(--chat-accent-strong)]" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-medium text-[var(--chat-text)] mb-1">{personality.greeting}</h2>
              <p className="text-sm text-[var(--chat-muted)]">{personality.subtitle}</p>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((msg, idx) => {
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
                  <MessageBubble message={msg} userPrompt={precedingUserPrompt} />
                </div>
              );
            })}
            {showThinking && (
              <ThinkingIndicator
                statusMessage={statusMessage}
                latestThought={latestThought}
                pipelineSteps={pipelineSteps}
                streamPhase={streamPhase}
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

      {/* Input */}
      <ChatInput
        onSend={(msg) => {
          sendMessage(msg, attachments);
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
    </div>
  );
}
