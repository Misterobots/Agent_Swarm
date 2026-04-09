"use client";

import { Palette } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { Style } from "@/types/chat";

const STYLES: { value: Style; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "concise", label: "Concise" },
  { value: "explanatory", label: "Explanatory" },
  { value: "formal", label: "Formal" },
  { value: "technical", label: "Technical" },
  { value: "casual", label: "Casual" },
];

export function StyleSelector() {
  const style = useSettingsStore((s) => s.style);
  const setStyle = useSettingsStore((s) => s.setStyle);

  return (
    <div className="relative inline-flex items-center">
      <Palette size={14} className="absolute left-2 pointer-events-none text-[var(--chat-muted)]" />
      <select
        value={style}
        onChange={(e) => setStyle(e.target.value as Style)}
        className={cn(
          "appearance-none pl-7 pr-6 py-1.5 rounded-md text-xs border cursor-pointer",
          "bg-[var(--chat-panel)] text-[var(--chat-text)] border-[var(--chat-border)]",
          "focus:border-[var(--chat-accent)] focus:outline-none",
          "hover:border-[var(--chat-accent)]",
          "transition-colors"
        )}
        title="Select response style"
      >
        {STYLES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      <svg
        className="absolute right-1.5 pointer-events-none text-[var(--chat-muted)]"
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="currentColor"
      >
        <path d="M2 3.5L5 7L8 3.5H2Z" />
      </svg>
    </div>
  );
}
