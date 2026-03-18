"use client";

import type { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { cn } from "@/lib/utils/cn";
import { Bot, User } from "lucide-react";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 py-4 px-4", isUser ? "bg-transparent" : "bg-[#0a0a14]")}>
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
          isUser ? "bg-cyan-900/40 text-cyan-400" : "bg-violet-900/40 text-violet-400"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className="flex-1 min-w-0 text-zinc-200">
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : message.content ? (
          <MarkdownRenderer content={message.content} />
        ) : (
          <span className="inline-block w-2 h-4 bg-cyan-400 animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  );
}
