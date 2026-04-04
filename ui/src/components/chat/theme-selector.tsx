"use client";

import { ChevronDown, Palette } from "lucide-react";
import { ChatTheme, useSettingsStore } from "@/lib/stores/settings-store";

const THEMES: Array<{ id: ChatTheme; label: string }> = [
  { id: "ember", label: "Ember" },
  { id: "slate", label: "Slate" },
  { id: "signal", label: "Signal" },
  { id: "office", label: "Office" },
  { id: "hacker", label: "Hacker" },
  { id: "star-trek", label: "Star Trek" },
  { id: "cyberpunk", label: "Cyberpunk" },
  { id: "minimal", label: "Minimal" },
];

export function ThemeSelector() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);

  return (
    <div className="relative inline-flex items-center">
      <Palette size={13} className="absolute left-2 text-[var(--chat-muted)] pointer-events-none" />
      <select
        value={theme}
        onChange={(e) => setTheme(e.target.value as ChatTheme)}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-sm border border-[var(--chat-border)] rounded-lg pl-7 pr-8 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer"
        title="Chat theme"
      >
        {THEMES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="absolute right-2 text-[var(--chat-muted)] pointer-events-none" />
    </div>
  );
}
