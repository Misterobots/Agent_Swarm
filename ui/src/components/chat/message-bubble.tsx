"use client";

import type { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { cn } from "@/lib/utils/cn";
import { Bot, User, Palette } from "lucide-react";
import Link from "next/link";

interface MessageBubbleProps {
  message: ChatMessage;
}

function isCreativeRedirect(content: string): boolean {
  return content.includes("Creative Request Detected") || content.includes("Switch to the **Art Studio**");
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showArtButton = !isUser && message.content && isCreativeRedirect(message.content);

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
          <>
            <MarkdownRenderer content={message.content} />
            {showArtButton && (
              <Link
                href="/art-studio"
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors shadow-lg shadow-violet-900/30"
              >
                <Palette size={16} />
                Open Art Studio
              </Link>
            )}
          </>
        ) : (
          <span className="inline-block w-2 h-4 bg-cyan-400 animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  );
}
