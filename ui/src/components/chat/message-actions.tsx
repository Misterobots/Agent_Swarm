"use client";

import { Copy, Pencil, RotateCcw, GitBranch, Check, Bookmark } from "lucide-react";
import { useState, useCallback } from "react";
import { cn } from "@/lib/utils/cn";

interface MessageActionsProps {
  content: string;
  isUser: boolean;
  onEdit?: () => void;
  onRetry?: () => void;
  onBranch?: () => void;
  /** Called when the user clicks the Flag button (assistant messages only). */
  onFlagClick?: () => void;
  /** True when this message already has a flag — hides the Flag button. */
  flagged?: boolean;
}

export function MessageActions({ content, isUser, onEdit, onRetry, onBranch, onFlagClick, flagged }: MessageActionsProps) {
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
      {/* Flag for follow-up — assistant messages only, hidden once already flagged */}
      {!isUser && onFlagClick && !flagged && (
        <ActionButton
          icon={<Bookmark size={12} />}
          title="Flag for follow-up"
          onClick={onFlagClick}
        />
      )}
      {/* Filled bookmark when already flagged (visual confirmation) */}
      {!isUser && flagged && (
        <span
          className="p-1 text-[var(--chat-accent)] opacity-70"
          title="Already flagged for follow-up"
        >
          <Bookmark size={12} fill="currentColor" />
        </span>
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
