"use client";

import { useEffect, useRef } from "react";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { useChatStore } from "@/lib/stores/chat-store";
import { MessageBubble } from "./message-bubble";
import { ThinkingIndicator } from "./thinking-indicator";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { Bot, Brain } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { ChatStatusBar } from "./chat-status-bar";
import { useSettingsStore } from "@/lib/stores/settings-store";

function usageBarClass(pct: number): string {
  if (pct >= 0.95) return "bg-red-500";
  if (pct >= 0.85) return "bg-orange-500";
  if (pct >= 0.7) return "bg-amber-500";
  return "bg-zinc-500";
}

export function ChatView() {
  const { messages, isStreaming, statusMessage, latestThought, tokenUsage, sendMessage, compactConversation, stopGeneration } = useChatStream();
  const { activeConversationId, activeConversation, updateConversation } = useChatStore();
  const model = useSettingsStore((s) => s.model);
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeConv = activeConversation();

  // Show the thinking indicator when streaming and either we have a status
  // message or the assistant message is still empty (waiting for first content)
  const lastMsg = messages[messages.length - 1];
  const showThinking =
    isStreaming &&
    (statusMessage !== null || (lastMsg?.role === "assistant" && !lastMsg.content));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, lastMsg?.content, statusMessage]);

  return (
    <div className="chat-shell flex flex-col h-full" data-route="chat">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-[#0e1117] px-4 py-2">
        <div className="flex items-center gap-3">
          <ModelSelector />
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
                  ? "bg-cyan-900/30 text-cyan-300 border-cyan-700/60"
                  : "bg-zinc-900/60 text-zinc-400 border-zinc-700/60"
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
            className="w-44 h-2 rounded-full bg-zinc-800 overflow-hidden border border-zinc-700"
            title={`Context usage: ${(tokenUsage.pct * 100).toFixed(1)}% (${tokenUsage.used}/${tokenUsage.total}) - Click to compact`}
          >
            <div
              className={cn("h-full transition-all", usageBarClass(tokenUsage.pct))}
              style={{ width: `${Math.min(100, tokenUsage.pct * 100)}%` }}
            />
          </button>
          <span className="text-xs text-zinc-400 min-w-[3rem]">
            {(tokenUsage.pct * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700">
        {tokenUsage.pct >= 0.95 && (
          <div className="mx-auto max-w-3xl mt-3 px-4">
            <div className="rounded-md border border-orange-900/60 bg-orange-950/30 px-3 py-2 text-xs text-orange-200">
              Context is near capacity. Compact now to preserve response quality.
            </div>
          </div>
        )}
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-violet-900/20 flex items-center justify-center">
              <Bot size={32} className="text-violet-400" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-medium text-zinc-300 mb-1">Hive Mind</h2>
              <p className="text-sm text-zinc-500">Send a message to start a conversation</p>
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
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  userPrompt={precedingUserPrompt}
                />
              );
            })}
            {showThinking && <ThinkingIndicator statusMessage={statusMessage} latestThought={latestThought} />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput
        onSend={sendMessage}
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
