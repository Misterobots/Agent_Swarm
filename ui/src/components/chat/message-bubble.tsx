"use client";

import { useState } from "react";
import type { ChatMessage } from "@/types/chat";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { cn } from "@/lib/utils/cn";
import { Bot, User, Palette, ChevronDown } from "lucide-react";
import Link from "next/link";
import { ToolCallBlock } from "./tool-call-block";

interface MessageBubbleProps {
  message: ChatMessage;
  userPrompt?: string;
}

function isCreativeRedirect(content: string): boolean {
  return content.includes("Creative Request Detected") || content.includes("Switch to the **Art Studio**");
}

export function MessageBubble({ message, userPrompt }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showArtButton = !isUser && message.content && isCreativeRedirect(message.content);
  const [traceOpen, setTraceOpen] = useState(false);
  const artStudioHref = userPrompt
    ? `/art-studio?prompt=${encodeURIComponent(userPrompt)}`
    : "/art-studio";

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
                href={artStudioHref}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors shadow-lg shadow-violet-900/30"
              >
                <Palette size={16} />
                Open Art Studio
              </Link>
            )}
            {!!message.thoughtTrace?.length && (
              <div className="mt-3 border border-zinc-800 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setTraceOpen((v) => !v)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-zinc-300 bg-zinc-900/60 hover:bg-zinc-800/70"
                >
                  <span>Agent Trace ({message.thoughtTrace.length})</span>
                  <ChevronDown
                    size={14}
                    className={cn("transition-transform", traceOpen ? "rotate-180" : "")}
                  />
                </button>
                {traceOpen && (
                  <div className="px-3 py-2 bg-zinc-950/70">
                    {message.thoughtTrace.map((t, idx) => (
                      <p key={`${t.timestamp}-${idx}`} className="text-xs text-cyan-300/85 font-mono py-0.5">
                        [{new Date(t.timestamp).toLocaleTimeString()}] {t.content}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
            {!!message.toolCalls?.length && <ToolCallBlock toolCalls={message.toolCalls} />}
          </>
        ) : (
          <span className="inline-block w-2 h-4 bg-cyan-400 animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  );
}
