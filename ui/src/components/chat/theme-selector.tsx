"use client";

import { useState, useRef, useEffect } from "react";
import { Palette, Check, Flame, Cpu, Zap, Briefcase, Terminal, Rocket, Sparkles, Globe } from "lucide-react";
import { ChatTheme, useSettingsStore } from "@/lib/stores/settings-store";

const THEMES: Array<{
  id: ChatTheme;
  label: string;
  icon: typeof Flame;
  desc: string;
  preview: { bg: string; accent: string; accent2: string };
}> = [
  { id: "ember", label: "Ember", icon: Flame, desc: "Warm forge aesthetic", preview: { bg: "#0f141c", accent: "#c97a5e", accent2: "#5f96d8" } },
  { id: "slate", label: "Slate", icon: Cpu, desc: "Cool architectural blue", preview: { bg: "#11161d", accent: "#4ba6c7", accent2: "#7a8ce0" } },
  { id: "signal", label: "Signal", icon: Zap, desc: "Radio operator gold", preview: { bg: "#171a1b", accent: "#d89a4d", accent2: "#8ba7b3" } },
  { id: "office", label: "Office", icon: Briefcase, desc: "Professional & clean", preview: { bg: "#f5f5f5", accent: "#2e5090", accent2: "#1a73e8" } },
  { id: "hacker", label: "Hacker", icon: Terminal, desc: "Green-on-black terminal", preview: { bg: "#0a0e27", accent: "#39ff14", accent2: "#00ff00" } },
  { id: "star-trek", label: "Star Trek", icon: Rocket, desc: "LCARS starship bridge", preview: { bg: "#0a141f", accent: "#0fa3b1", accent2: "#ffd700" } },
  { id: "cyberpunk", label: "Cyberpunk", icon: Sparkles, desc: "Neon-soaked future", preview: { bg: "#0d0221", accent: "#ff10f0", accent2: "#00ffff" } },
  { id: "minimal", label: "Minimal", icon: Globe, desc: "Clean & distraction-free", preview: { bg: "#fafafa", accent: "#2c2c2c", accent2: "#666666" } },
];

export function ThemeSelector() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const current = THEMES.find((t) => t.id === theme) || THEMES[0];
  const CurrentIcon = current.icon;

  return (
    <div ref={ref} className="relative">
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border border-[var(--chat-border)] bg-[var(--chat-panel)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] transition-colors"
        title="Select theme"
      >
        <CurrentIcon size={14} className="text-[var(--chat-accent)]" />
        <span>{current.label}</span>
        <Palette size={12} className="text-[var(--chat-muted)]" />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 top-full mt-2 z-50 w-64 rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] shadow-2xl overflow-hidden theme-picker-enter">
          <div className="px-3 py-2 border-b border-[var(--chat-border)]">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--chat-muted)]">Select Theme</span>
          </div>
          <div className="p-2 grid gap-1 max-h-80 overflow-y-auto scrollbar-thin">
            {THEMES.map((t) => {
              const Icon = t.icon;
              const isActive = t.id === theme;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setTheme(t.id); setOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-left transition-all ${
                    isActive
                      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
                      : "hover:bg-[var(--chat-soft)] border border-transparent"
                  }`}
                >
                  {/* Color preview swatch */}
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg overflow-hidden border border-[var(--chat-border)] relative" style={{ background: t.preview.bg }}>
                    <div className="absolute bottom-0 left-0 w-full h-1.5" style={{ background: `linear-gradient(90deg, ${t.preview.accent}, ${t.preview.accent2})` }} />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Icon size={14} style={{ color: t.preview.accent }} />
                    </div>
                  </div>
                  {/* Label + description */}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--chat-text)]">{t.label}</div>
                    <div className="text-[10px] text-[var(--chat-muted)] truncate">{t.desc}</div>
                  </div>
                  {/* Active check */}
                  {isActive && <Check size={16} className="text-[var(--chat-accent)] flex-shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
