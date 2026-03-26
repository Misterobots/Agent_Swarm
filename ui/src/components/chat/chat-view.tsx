"use client";

import { useEffect, useRef } from "react";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { MessageBubble } from "./message-bubble";
import { ThinkingIndicator } from "./thinking-indicator";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { Bot } from "lucide-react";

export function ChatView() {
  const { messages, isStreaming, statusMessage, sendMessage, stopGeneration } = useChatStream();
  const bottomRef = useRef<HTMLDivElement>(null);

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
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-[#0e1117] px-4 py-2">
        <div className="flex items-center gap-3">
          <ModelSelector />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700">
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
            {showThinking && <ThinkingIndicator statusMessage={statusMessage} />}
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
    </div>
  );
}
