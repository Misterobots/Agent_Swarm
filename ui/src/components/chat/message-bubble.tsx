"use client";

import type { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { cn } from "@/lib/utils/cn";
import { Bot, User } from "lucide-react";

interface MessageBubbleProps {
  message: ChatMessage;
  userPrompt?: string;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 py-4 px-4", isUser ? "bg-transparent" : "bg-[color:color-mix(in_srgb,var(--chat-surface)_80%,black)]")}>
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
          isUser ? "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_20%,transparent)] text-[var(--chat-accent-2)]" : "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] text-[var(--chat-accent-strong)]"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className="flex-1 min-w-0 text-[var(--chat-text)]">
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : message.content ? (
          <MarkdownRenderer content={message.content} />
        ) : (
          <span className="inline-block w-2 h-4 rounded-sm animate-pulse" style={{ backgroundColor: "var(--chat-accent)" }} />
        )}
      </div>
    </div>
  );
}
