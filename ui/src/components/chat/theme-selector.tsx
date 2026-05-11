"use client";

import { useState, useRef, useEffect } from "react";
import { Sun, Moon, Monitor, Check, Tv2 } from "lucide-react";
import { useSettingsStore, type ThemeMode } from "@/lib/stores/settings-store";

const MODES: Array<{ id: ThemeMode; label: string; icon: typeof Sun; desc: string }> = [
  { id: "system", label: "System",  icon: Monitor, desc: "Match OS preference" },
  { id: "dark",   label: "Dark",    icon: Moon,    desc: "Memex Dark" },
  { id: "light",  label: "Light",   icon: Sun,     desc: "Memex Light" },
];

interface NamedTheme {
  id: string;
  label: string;
  desc: string;
  swatch: { bg: string; accent: string; accent2: string };
}

/** First-class named themes (always available, no debug flag needed). */
const NAMED_THEMES: NamedTheme[] = [
  {
    id: "lcars",
    label: "LCARS Amber",
    desc: "Lower Decks warm palette",
    swatch: { bg: "#080600", accent: "#FFAA00", accent2: "#FF5500" },
  },
  {
    id: "lcars-blue",
    label: "LCARS Blue",
    desc: "TNG cold palette",
    swatch: { bg: "#02040E", accent: "#5577FF", accent2: "#AA66FF" },
  },
  {
    id: "lcars-teal",
    label: "LCARS Teal",
    desc: "Green-teal palette",
    swatch: { bg: "#020E08", accent: "#00CC77", accent2: "#FF6600" },
  },
];

export function ThemeSelector() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
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

  const isNamed = theme !== "memex";
  const currentNamed = NAMED_THEMES.find((t) => t.id === theme);
  const currentMode = MODES.find((m) => m.id === themeMode) ?? MODES[0];
  const ModeIcon = currentMode.icon;

  const triggerLabel = currentNamed?.label ?? currentMode.label;
  const TriggerIcon = currentNamed ? Tv2 : ModeIcon;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs border border-[var(--chat-border)] bg-[var(--chat-panel)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] transition-colors"
        title="Theme"
        aria-label={`Theme: ${triggerLabel}`}
      >
        <TriggerIcon size={14} className="text-[var(--chat-accent)]" />
        <span className="hidden sm:inline">{triggerLabel}</span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-50 w-56 rounded-md border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden theme-picker-enter"
          style={{ boxShadow: "var(--elev-3)" }}
        >
          {/* Memex modes */}
          <div className="px-3 py-2 border-b border-[var(--chat-border)]">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              Memex
            </span>
          </div>
          <div className="p-1">
            {MODES.map((m) => {
              const Icon = m.icon;
              const isActive = theme === "memex" && m.id === themeMode;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setTheme("memex");
                    setThemeMode(m.id);
                    setOpen(false);
                  }}
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

          {/* Named themes */}
          <div className="px-3 py-2 border-t border-[var(--chat-border)]">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              Themes
            </span>
          </div>
          <div className="p-1">
            {NAMED_THEMES.map((t) => {
              const isActive = theme === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setTheme(t.id as typeof theme); setOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2 rounded-md text-left transition-colors ${
                    isActive
                      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_12%,transparent)] text-[var(--chat-accent-strong)]"
                      : "hover:bg-[var(--hover-tint)] text-[var(--chat-text)]"
                  }`}
                >
                  {/* Colour swatch */}
                  <div
                    className="w-7 h-7 rounded-sm flex-shrink-0 overflow-hidden border"
                    style={{ background: t.swatch.bg, borderColor: t.swatch.accent }}
                  >
                    <div className="h-full flex flex-col">
                      <div className="flex-1" style={{ background: t.swatch.accent }} />
                      <div className="flex-1" style={{ background: t.swatch.accent2 }} />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--chat-text)]">{t.label}</div>
                    <div className="text-[10px] text-[var(--chat-muted)] truncate">{t.desc}</div>
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
