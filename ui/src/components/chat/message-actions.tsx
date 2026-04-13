"use client";

import { Copy, Pencil, RotateCcw, GitBranch, Check } from "lucide-react";
import { useState, useCallback } from "react";
import { cn } from "@/lib/utils/cn";

interface MessageActionsProps {
  content: string;
  isUser: boolean;
  onEdit?: () => void;
  onRetry?: () => void;
  onBranch?: () => void;
}

export function MessageActions({ content, isUser, onEdit, onRetry, onBranch }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API not available
    }
  }, [content]);

  return (
    <div
      className={cn(
        "message-actions absolute -top-3 flex items-center gap-0.5 px-1 py-0.5 rounded-md",
        "bg-[var(--chat-panel)] border border-[var(--chat-border)] shadow-sm",
        "opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10",
        isUser ? "right-2" : "right-2"
      )}
    >
      <ActionButton
        icon={copied ? <Check size={12} /> : <Copy size={12} />}
        title="Copy message"
        onClick={handleCopy}
        active={copied}
      />
      {isUser && onEdit && (
        <ActionButton icon={<Pencil size={12} />} title="Edit message" onClick={onEdit} />
      )}
      {isUser && onRetry && (
        <ActionButton icon={<RotateCcw size={12} />} title="Retry from here" onClick={onRetry} />
      )}
      {onBranch && (
        <ActionButton icon={<GitBranch size={12} />} title="Branch conversation" onClick={onBranch} />
      )}
    </div>
  );
}

function ActionButton({
  icon,
  title,
  onClick,
  active = false,
}: {
  icon: React.ReactNode;
  title: string;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={cn(
        "p-1 rounded transition-colors",
        active
          ? "text-[var(--chat-accent)]"
          : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-soft)]"
      )}
    >
      {icon}
    </button>
  );
}
