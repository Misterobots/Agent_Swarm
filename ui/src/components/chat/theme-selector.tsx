"use client";

import { useSettingsStore, type ChatTheme } from "@/lib/stores/settings-store";
import { useEffect } from "react";
import { Palette } from "lucide-react";

const THEMES: { id: ChatTheme; label: string }[] = [
  { id: "hive", label: "Hive" },
  { id: "neon", label: "Neon" },
  { id: "ember", label: "Ember" },
  { id: "forest", label: "Forest" },
];

export function ThemeSelector() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);

  // Apply data-theme to <html> so CSS vars cascade to .chat-shell
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  return (
    <div className="relative inline-flex items-center">
      <Palette size={14} className="absolute left-2 text-[var(--chat-muted)] pointer-events-none z-10" />
      <select
        value={theme}
        onChange={(e) => setTheme(e.target.value as ChatTheme)}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-xs border border-[var(--chat-border)] rounded-lg pl-7 pr-6 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer"
      >
        {THEMES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </div>
  );
}
