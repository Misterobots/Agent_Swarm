"use client";

import { useState, useRef, useEffect } from "react";
import { Sun, Moon, Monitor, Check } from "lucide-react";
import { useSettingsStore, type ThemeMode } from "@/lib/stores/settings-store";

const MODES: Array<{ id: ThemeMode; label: string; icon: typeof Sun; desc: string }> = [
  { id: "system", label: "System",  icon: Monitor, desc: "Match OS preference" },
  { id: "dark",   label: "Dark",    icon: Moon,    desc: "Memex Dark" },
  { id: "light",  label: "Light",   icon: Sun,     desc: "Memex Light" },
];

export function ThemeSelector() {
  const themeMode = useSettingsStore((s) => s.themeMode);
  const setThemeMode = useSettingsStore((s) => s.setThemeMode);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const current = MODES.find((m) => m.id === themeMode) ?? MODES[0];
  const CurrentIcon = current.icon;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs border border-[var(--chat-border)] bg-[var(--chat-panel)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] transition-colors"
        title="Theme mode"
        aria-label={`Theme: ${current.label}`}
      >
        <CurrentIcon size={14} className="text-[var(--chat-accent)]" />
        <span className="hidden sm:inline">{current.label}</span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-50 w-52 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden theme-picker-enter"
          style={{ boxShadow: "var(--elev-3)" }}
        >
          <div className="px-3 py-2 border-b border-[var(--chat-border)]">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--chat-muted)]">
              Memex
            </span>
          </div>
          <div className="p-1">
            {MODES.map((m) => {
              const Icon = m.icon;
              const isActive = m.id === themeMode;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => { setThemeMode(m.id); setOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-md text-left transition-colors ${
                    isActive
                      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_12%,transparent)] text-[var(--chat-accent-strong)]"
                      : "hover:bg-[var(--hover-tint)] text-[var(--chat-text)]"
                  }`}
                >
                  <Icon size={15} className={isActive ? "text-[var(--chat-accent)]" : "text-[var(--chat-muted)]"} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{m.label}</div>
                    <div className="text-[10px] text-[var(--chat-muted)] truncate">{m.desc}</div>
                  </div>
                  {isActive && <Check size={14} className="text-[var(--chat-accent)] flex-shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
