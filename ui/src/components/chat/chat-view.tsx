"use client";

import { useEffect, useRef } from "react";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import { ModelSelector } from "./model-selector";
import { NodeStatus } from "@/components/shared/node-status";
import { Bot } from "lucide-react";

export function ChatView() {
  const { messages, isStreaming, sendMessage, stopGeneration } = useChatStream();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, messages[messages.length - 1]?.content]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-[#0e1117] px-4 py-2">
        <div className="flex items-center gap-3">
          <ModelSelector />
          <NodeStatus />
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
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
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
