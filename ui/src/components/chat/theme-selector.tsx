"use client";

import { useState, useRef, useEffect } from "react";
import { Sun, Moon, Monitor, ChevronDown, Check } from "lucide-react";
import { useSettingsStore, type ThemeMode } from "@/lib/stores/settings-store";
import { cn } from "@/lib/utils/cn";

const MEMEX_MODES: Array<{ id: ThemeMode; icon: typeof Sun; label: string }> = [
  { id: "system", icon: Monitor, label: "System" },
  { id: "dark",   icon: Moon,   label: "Dark"   },
  { id: "light",  icon: Sun,    label: "Light"  },
];

const LCARS_VARIANTS = [
  { id: "lcars",      label: "Amber", dot: "#FFAA00" },
  { id: "lcars-blue", label: "Blue",  dot: "#5577FF" },
  { id: "lcars-teal", label: "Teal",  dot: "#00CC77" },
] as const;

interface NamedTheme {
  id: string;
  label: string;
  desc: string;
  dots: string[];
}

const NAMED_THEMES: NamedTheme[] = [
  {
    id: "cyberpunk",
    label: "Shadowrun",
    desc: "AR matrix overlay — teal & magenta",
    dots: ["#00DDC0", "#CC44FF"],
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

  const isLcars = theme.startsWith("lcars");
  const isNamed = !isLcars && theme !== "memex";
  const lcarsVariant = LCARS_VARIANTS.find((v) => v.id === theme);
  const namedTheme = NAMED_THEMES.find((t) => t.id === theme);
  const memexMode = MEMEX_MODES.find((m) => m.id === themeMode) ?? MEMEX_MODES[0];

  const triggerLabel = isLcars
    ? `LCARS · ${lcarsVariant?.label ?? "Amber"}`
    : namedTheme
    ? namedTheme.label
    : `Memex · ${memexMode.label}`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs border border-[var(--chat-border)] bg-[var(--chat-panel)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] transition-colors"
        aria-label={`Theme: ${triggerLabel}`}
      >
        {isLcars ? (
          <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: lcarsVariant?.dot ?? "#FFAA00" }} />
        ) : namedTheme ? (
          <span className="flex gap-0.5">
            {namedTheme.dots.map((d, i) => (
              <span key={i} className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: d }} />
            ))}
          </span>
        ) : (
          <memexMode.icon size={13} className="text-[var(--chat-accent)]" />
        )}
        <span>{triggerLabel}</span>
        <ChevronDown size={12} className={cn("text-[var(--chat-muted)] transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-50 w-64 rounded-md border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden theme-picker-enter"
          style={{ boxShadow: "var(--elev-3)" }}
        >
          {/* Memex family */}
          <div className="p-3 space-y-2">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              Memex
            </div>
            <div className="flex gap-1">
              {MEMEX_MODES.map((m) => {
                const Icon = m.icon;
                const active = !isLcars && themeMode === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => { setTheme("memex"); setThemeMode(m.id); setOpen(false); }}
                    className={cn(
                      "flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 text-[11px] rounded-sm border transition-colors",
                      active
                        ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] border-[color:color-mix(in_srgb,var(--chat-accent)_50%,var(--chat-border))] text-[var(--chat-accent-strong)]"
                        : "bg-[var(--chat-panel)] border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_60%,var(--chat-text))]"
                    )}
                  >
                    <Icon size={11} />
                    <span>{m.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* LCARS family */}
          <div className="p-3 space-y-2 border-t border-[var(--chat-border)]">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              LCARS
            </div>
            <div className="flex gap-1">
              {LCARS_VARIANTS.map((v) => {
                const active = theme === v.id;
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => { setTheme(v.id); setOpen(false); }}
                    className={cn(
                      "flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 text-[11px] rounded-sm border transition-colors",
                      active
                        ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] border-[color:color-mix(in_srgb,var(--chat-accent)_50%,var(--chat-border))] text-[var(--chat-accent-strong)]"
                        : "bg-[var(--chat-panel)] border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_60%,var(--chat-text))]"
                    )}
                  >
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: v.dot }} />
                    <span>{v.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Named single-variant themes */}
          {NAMED_THEMES.map((t) => {
            const active = theme === t.id;
            return (
              <div key={t.id} className="p-3 space-y-2 border-t border-[var(--chat-border)]">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
                  {t.label}
                </div>
                <button
                  type="button"
                  onClick={() => { setTheme(t.id as Parameters<typeof setTheme>[0]); setOpen(false); }}
                  className={cn(
                    "w-full inline-flex items-center gap-2 px-2.5 py-2 text-[12px] rounded-sm border transition-colors",
                    active
                      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] border-[color:color-mix(in_srgb,var(--chat-accent)_50%,var(--chat-border))] text-[var(--chat-accent-strong)]"
                      : "bg-[var(--chat-panel)] border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_60%,var(--chat-text))]"
                  )}
                >
                  <span className="flex gap-0.5">
                    {t.dots.map((d, i) => (
                      <span key={i} className="w-2.5 h-2.5 rounded-full" style={{ background: d }} />
                    ))}
                  </span>
                  <span className="flex-1 text-left">{t.desc}</span>
                  {active && <Check size={13} className="text-[var(--chat-accent)] flex-shrink-0" />}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
