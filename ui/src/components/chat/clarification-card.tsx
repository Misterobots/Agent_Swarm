"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import type { ClarificationCard } from "@/types/chat";
import { cn } from "@/lib/utils/cn";

interface ClarificationCardProps {
  card: ClarificationCard;
  onSelect: (value: string) => void;
  disabled?: boolean;
}

export function ClarificationCard({ card, onSelect, disabled }: ClarificationCardProps) {
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(null);
  const [freetext, setFreetext] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleOption = (value: string, redirect?: string) => {
    if (disabled || selected) return;
    setSelected(value);
    if (redirect) {
      // Pure navigation — no backend round-trip, just go there directly
      router.push(redirect);
    } else {
      onSelect(value);
    }
  };

  const handleFreetext = () => {
    const text = freetext.trim();
    if (!text || disabled || selected) return;
    setSelected(text);
    onSelect(text);
  };

  const headerColor =
    card.card_type === "dev_mode_gate"
      ? "bg-cyan-950/30 border-cyan-700/40"
      : card.card_type === "dev_project"
      ? "bg-blue-950/30 border-blue-700/40"
      : card.card_type === "onboarding"
      ? "bg-emerald-950/30 border-emerald-700/40"
      : "bg-amber-950/30 border-amber-700/40";

  const headerText =
    card.card_type === "dev_mode_gate"
      ? "text-cyan-200"
      : card.card_type === "dev_project"
      ? "text-blue-200"
      : card.card_type === "onboarding"
      ? "text-emerald-200"
      : "text-amber-200";

  const headerBorder =
    card.card_type === "dev_mode_gate"
      ? "border-cyan-700/50"
      : card.card_type === "dev_project"
      ? "border-blue-700/50"
      : card.card_type === "onboarding"
      ? "border-emerald-700/50"
      : "border-amber-700/50";

  const optionHover =
    card.card_type === "dev_mode_gate"
      ? "hover:border-cyan-600 hover:text-cyan-300"
      : card.card_type === "dev_project"
      ? "hover:border-blue-600 hover:text-blue-300"
      : card.card_type === "onboarding"
      ? "hover:border-emerald-600 hover:text-emerald-300"
      : "hover:border-amber-600 hover:text-amber-300";

  const selectedStyle =
    card.card_type === "dev_mode_gate"
      ? "border-cyan-600 text-cyan-300 bg-cyan-900/20"
      : card.card_type === "dev_project"
      ? "border-blue-600 text-blue-300 bg-blue-900/20"
      : card.card_type === "onboarding"
      ? "border-emerald-600 text-emerald-300 bg-emerald-900/20"
      : "border-amber-600 text-amber-300 bg-amber-900/20";

  return (
    <div className={cn("mt-3 rounded-md border overflow-hidden", headerBorder)}>
      {/* Header */}
      <div className={cn("px-3 py-2 border-b", headerColor, headerBorder)}>
        <span className={cn("text-xs font-semibold", headerText)}>
          {card.card_type === "dev_mode_gate"
            ? "⚡ Dev Mode Required"
            : card.card_type === "dev_project"
            ? "🛠️ Project Setup"
            : card.card_type === "onboarding"
            ? "🚀 New Project"
            : "🤔 Clarification Needed"}
        </span>
      </div>

      <div className="px-3 py-3 space-y-3 bg-[var(--chat-bg)]">
        {/* Context paragraph */}
        {card.context && (
          <p className="text-xs text-[var(--chat-muted)] leading-relaxed">{card.context}</p>
        )}

        {/* Question */}
        <p className="text-sm text-[var(--chat-text)] font-medium leading-snug">{card.question}</p>

        {/* Option chips */}
        {card.options.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {card.options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                disabled={!!(disabled || selected)}
                onClick={() => handleOption(opt.value, opt.redirect)}
                className={cn(
                  "px-3 py-2 text-xs rounded-md border transition-colors text-left",
                  selected === opt.value
                    ? selectedStyle
                    : "border-[var(--chat-border)] text-[var(--chat-muted)] bg-[var(--chat-panel)]",
                  !(disabled || selected) && optionHover,
                  (disabled || (selected && selected !== opt.value)) && "opacity-40 cursor-default"
                )}
              >
                <span className="block font-medium leading-snug">{opt.label}</span>
                {opt.description && (
                  <span className="block mt-0.5 text-[10px] opacity-60 font-normal leading-snug">{opt.description}</span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Freetext input */}
        {card.allow_freetext && !selected && (
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={freetext}
              onChange={(e) => setFreetext(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFreetext()}
              disabled={!!(disabled || selected)}
              placeholder="Or type your answer…"
              className="flex-1 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)] px-2.5 py-1.5 text-xs text-[var(--chat-text)] placeholder-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)] transition-colors"
            />
            <button
              type="button"
              onClick={handleFreetext}
              disabled={!freetext.trim() || !!(disabled || selected)}
              className="px-3 py-1.5 text-xs rounded-md border border-[var(--chat-border)] text-[var(--chat-muted)] hover:border-[var(--chat-accent)] hover:text-[var(--chat-text)] disabled:opacity-40 disabled:cursor-default transition-colors"
            >
              Send
            </button>
          </div>
        )}

        {/* Answered state */}
        {selected && (
          <p className="text-[10px] text-[var(--chat-muted)] italic">
            ✓ Answered — waiting for response…
          </p>
        )}
      </div>
    </div>
  );
}
