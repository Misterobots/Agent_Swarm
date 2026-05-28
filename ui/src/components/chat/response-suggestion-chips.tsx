"use client";

/**
 * ResponseSuggestionChips — end-of-response interactive chip row.
 *
 * Renders after every non-streaming assistant message that has
 * suggestedFollowups attached:
 *   - 2 LLM-generated contextual chips (backend-provided)
 *   - 1 theme-voiced generic chip ("Go deeper" / "dig deeper" / etc.)
 *   - Free-text input to chain into a new turn
 *
 * Styling follows the existing ClarificationCard pattern: rounded-full
 * borders, theme-aware var(--chat-*) tokens, hover states, selected state.
 */

import { useState, useRef } from "react";
import type { SuggestedFollowup } from "@/types/chat";
import { THEME_GENERIC_FOLLOWUP } from "@/lib/themes/personalities";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { cn } from "@/lib/utils/cn";
import { Sparkles, ArrowRight } from "lucide-react";

interface ResponseSuggestionChipsProps {
  followups: SuggestedFollowup[];
  /** Called when the user selects a chip or submits free text */
  onSelect: (prompt: string) => void;
  /** Disable interaction (e.g. when a new turn is already streaming) */
  disabled?: boolean;
}

export function ResponseSuggestionChips({
  followups,
  onSelect,
  disabled = false,
}: ResponseSuggestionChipsProps) {
  const theme = useSettingsStore((s) => s.theme);
  const [selected, setSelected] = useState<string | null>(null);
  const [freetext, setFreetext] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Take the first 2 contextual chips + 1 theme-voiced generic chip
  const contextual = followups.slice(0, 2);
  const generic = THEME_GENERIC_FOLLOWUP[theme] ?? THEME_GENERIC_FOLLOWUP.memex;

  const handleChip = (prompt: string) => {
    if (disabled || selected) return;
    setSelected(prompt);
    onSelect(prompt);
  };

  const handleFreetext = () => {
    const text = freetext.trim();
    if (!text || disabled || selected) return;
    setSelected(text);
    onSelect(text);
  };

  return (
    <div className="mt-3 flex flex-col gap-2">
      {/* Header — small, unobtrusive */}
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-[var(--chat-muted)] opacity-70">
        <Sparkles size={10} className="text-[var(--chat-accent)]" />
        <span>Suggested follow-ups</span>
      </div>

      {/* Chip row */}
      <div className="flex flex-wrap gap-2">
        {contextual.map((chip, idx) => (
          <Chip
            key={`ctx-${idx}`}
            label={chip.label}
            description={chip.prompt}
            onClick={() => handleChip(chip.prompt)}
            selected={selected === chip.prompt}
            disabled={disabled || !!selected}
            variant="contextual"
          />
        ))}
        <Chip
          key="generic"
          label={generic.label}
          description={generic.prompt}
          onClick={() => handleChip(generic.prompt)}
          selected={selected === generic.prompt}
          disabled={disabled || !!selected}
          variant="generic"
        />
      </div>

      {/* Free-text input — always available unless something already selected */}
      {!selected && (
        <div className="flex items-center gap-2 mt-1">
          <input
            ref={inputRef}
            type="text"
            value={freetext}
            onChange={(e) => setFreetext(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFreetext()}
            disabled={disabled}
            placeholder="Or type your own follow-up…"
            className={cn(
              "flex-1 rounded-md border bg-[var(--chat-panel)] px-2.5 py-1.5 text-xs",
              "border-[var(--chat-border)] text-[var(--chat-text)] placeholder-[var(--chat-muted)]",
              "focus:outline-none focus:border-[var(--chat-accent)] transition-colors",
              disabled && "opacity-40 cursor-not-allowed"
            )}
          />
          <button
            type="button"
            onClick={handleFreetext}
            disabled={!freetext.trim() || disabled}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs transition-colors",
              "border-[var(--chat-border)] text-[var(--chat-muted)]",
              "hover:border-[var(--chat-accent)] hover:text-[var(--chat-text)]",
              "disabled:opacity-40 disabled:cursor-default disabled:hover:border-[var(--chat-border)] disabled:hover:text-[var(--chat-muted)]"
            )}
            aria-label="Send custom follow-up"
          >
            Send <ArrowRight size={10} />
          </button>
        </div>
      )}

      {selected && (
        <p className="text-[10px] text-[var(--chat-muted)] italic">
          ✓ Following up — waiting for response…
        </p>
      )}
    </div>
  );
}

interface ChipProps {
  label: string;
  description: string;
  onClick: () => void;
  selected: boolean;
  disabled: boolean;
  variant: "contextual" | "generic";
}

function Chip({ label, description, onClick, selected, disabled, variant }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={description}
      className={cn(
        "px-3 py-1.5 text-xs rounded-full border transition-colors",
        selected
          ? "border-[var(--chat-accent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] text-[var(--chat-accent)]"
          : variant === "contextual"
          ? "border-[color:color-mix(in_srgb,var(--chat-accent)_35%,var(--chat-border))] bg-[var(--chat-panel)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] hover:text-[var(--chat-accent)]"
          : "border-[var(--chat-border)] bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:border-[var(--chat-accent)] hover:text-[var(--chat-text)]",
        disabled && !selected && "opacity-40 cursor-default hover:border-[var(--chat-border)] hover:text-[var(--chat-muted)]"
      )}
    >
      {label}
    </button>
  );
}
