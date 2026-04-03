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
    <div className={cn("flex gap-3 py-4 px-4", isUser ? "bg-transparent" : "bg-[var(--chat-surface)]")}>
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
          isUser
            ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_16%,transparent)] text-[var(--chat-accent-strong)] border border-[var(--chat-border)]"
            : "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_14%,transparent)] text-[var(--chat-accent-2)] border border-[var(--chat-border)]"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className="flex-1 min-w-0 text-[var(--chat-text)]">
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : message.content ? (
          <>
            <MarkdownRenderer content={message.content} />
            {showArtButton && (
              <Link
                href={artStudioHref}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--chat-accent-2)] hover:brightness-110 text-white text-sm font-medium transition-colors"
              >
                <Palette size={16} />
                Open Art Studio
              </Link>
            )}
            {!!message.thoughtTrace?.length && (
              <div className="mt-3 border border-[var(--chat-border)] rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setTraceOpen((v) => !v)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-[var(--chat-text)] bg-[var(--chat-panel)] hover:bg-[var(--chat-soft)]"
                >
                  <span>Agent Trace ({message.thoughtTrace.length})</span>
                  <ChevronDown
                    size={14}
                    className={cn("transition-transform", traceOpen ? "rotate-180" : "")}
                  />
                </button>
                {traceOpen && (
                  <div className="px-3 py-2 bg-[color:color-mix(in_srgb,var(--chat-panel)_90%,black)]">
                    {message.thoughtTrace.map((t, idx) => (
                      <p key={`${t.timestamp}-${idx}`} className="text-xs text-[var(--chat-accent-strong)] font-mono py-0.5">
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
          <span className="inline-block w-2 h-4 bg-[var(--chat-accent)] animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  );
}
