"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X, Check, Monitor, Sun, Moon } from "lucide-react";
import { useSettingsStore, type ThemeMode } from "@/lib/stores/settings-store";
import { cn } from "@/lib/utils/cn";

interface ThemeCard {
  id: string;
  label: string;
  desc: string;
  dots: string[];
  bg: string;
  accent: string;
}

const MEMEX_CARD: ThemeCard = {
  id: "memex", label: "Memex", desc: "Default — neutral with light/dark/system modes",
  dots: ["#6366f1", "#818cf8"], bg: "#0e1117", accent: "#6366f1",
};

const LCARS_CARDS: ThemeCard[] = [
  { id: "lcars",      label: "LCARS · Amber", desc: "Starfleet computer interface",      dots: ["#FFAA00"], bg: "#0a0600", accent: "#FFAA00" },
  { id: "lcars-blue", label: "LCARS · Blue",  desc: "Starfleet computer interface",      dots: ["#5577FF"], bg: "#00050a", accent: "#5577FF" },
  { id: "lcars-teal", label: "LCARS · Teal",  desc: "Starfleet computer interface",      dots: ["#00CC77"], bg: "#00060a", accent: "#00CC77" },
];

const EXTENDED_CARDS: ThemeCard[] = [
  { id: "cyberpunk",     label: "Cyberpunk",      desc: "AR matrix overlay",              dots: ["#00DDC0", "#CC44FF"], bg: "#020C0A", accent: "#00DDC0" },
  { id: "shadowrun",     label: "Shadowrun",       desc: "Decker AI in the Net",           dots: ["#00DDC0", "#CC44FF"], bg: "#020C0A", accent: "#00DDC0" },
  { id: "ops",           label: "Ops",             desc: "Mission control",                dots: ["#4C9FE8", "#E05C4C"], bg: "#050C1A", accent: "#4C9FE8" },
  { id: "terminal",      label: "Terminal",        desc: "Green phosphor on black",        dots: ["#33FF66", "#FFAA33"], bg: "#010601", accent: "#33FF66" },
  { id: "hal9000",       label: "HAL 9000",        desc: "I'm sorry Dave",                 dots: ["#CC0000"],           bg: "#000005", accent: "#CC0000" },
  { id: "nostromo",      label: "Nostromo",        desc: "MU/TH/UR crew interface",        dots: ["#FF8C00"],           bg: "#060400", accent: "#FF8C00" },
  { id: "tron",          label: "Tron",            desc: "On the Grid",                    dots: ["#00C8FF"],           bg: "#000008", accent: "#00C8FF" },
  { id: "bladerunner",   label: "Blade Runner",    desc: "Neon gold & blue in the rain",   dots: ["#D4900A", "#3D78FF"], bg: "#060305", accent: "#D4900A" },
  { id: "dune",          label: "Dune",            desc: "Spice-gold on desert dark",      dots: ["#E8881A"],           bg: "#0E0700", accent: "#E8881A" },
  { id: "memex-archive", label: "Memex Archive",   desc: "As we may think",                dots: ["#C8922A"],           bg: "#0E0A02", accent: "#C8922A" },
];

const MEMEX_MODES: Array<{ id: ThemeMode; icon: typeof Sun; label: string }> = [
  { id: "system", icon: Monitor, label: "System" },
  { id: "dark",   icon: Moon,    label: "Dark"   },
  { id: "light",  icon: Sun,     label: "Light"  },
];

function MiniPreview({ card, active }: { card: ThemeCard; active: boolean }) {
  return (
    <div
      className="relative rounded-md overflow-hidden flex-shrink-0"
      style={{
        width: 48, height: 36,
        background: card.bg,
        border: active ? `1.5px solid ${card.accent}` : "1px solid rgba(255,255,255,0.06)",
        boxShadow: active ? `0 0 8px ${card.accent}40` : undefined,
      }}
    >
      {/* Fake header bar */}
      <div className="absolute inset-x-0 top-0 h-2 flex items-center px-1 gap-0.5"
        style={{ background: `${card.accent}18` }}>
        {card.dots.slice(0, 2).map((d, i) => (
          <span key={i} className="rounded-full flex-shrink-0"
            style={{ width: 4, height: 4, background: d }} />
        ))}
      </div>
      {/* Fake content lines */}
      <div className="absolute inset-x-1 top-3 space-y-0.5">
        <div className="rounded-sm h-1.5" style={{ width: "70%", background: `${card.accent}50` }} />
        <div className="rounded-sm h-1" style={{ width: "90%", background: "rgba(255,255,255,0.08)" }} />
        <div className="rounded-sm h-1" style={{ width: "60%", background: "rgba(255,255,255,0.05)" }} />
      </div>
      {active && (
        <div className="absolute bottom-0.5 right-0.5 w-3 h-3 rounded-full flex items-center justify-center"
          style={{ background: card.accent }}>
          <Check size={8} color={card.bg} strokeWidth={3} />
        </div>
      )}
    </div>
  );
}

interface ThemeGalleryProps {
  open: boolean;
  onClose: () => void;
}

export function ThemeGallery({ open, onClose }: ThemeGalleryProps) {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const themeMode = useSettingsStore((s) => s.themeMode);
  const setThemeMode = useSettingsStore((s) => s.setThemeMode);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)" }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={panelRef}
        className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden theme-picker-enter"
        style={{ boxShadow: "var(--elev-3)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--chat-border)]">
          <h2 className="text-sm font-semibold text-[var(--chat-text)]">Theme Gallery</h2>
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Memex */}
          <section>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] mb-3">Memex</div>
            <div
              className={cn(
                "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                theme === "memex"
                  ? "border-[color:color-mix(in_srgb,var(--chat-accent)_60%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent)_8%,transparent)]"
                  : "border-[var(--chat-border)] bg-[var(--chat-panel)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))]"
              )}
              onClick={() => setTheme("memex")}
            >
              <MiniPreview card={MEMEX_CARD} active={theme === "memex"} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[var(--chat-text)]">{MEMEX_CARD.label}</div>
                <div className="text-xs text-[var(--chat-muted)] mt-0.5">{MEMEX_CARD.desc}</div>
                {theme === "memex" && (
                  <div className="flex gap-1 mt-2">
                    {MEMEX_MODES.map((m) => {
                      const Icon = m.icon;
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setThemeMode(m.id); }}
                          className={cn(
                            "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] border transition-colors",
                            themeMode === m.id
                              ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] border-[color:color-mix(in_srgb,var(--chat-accent)_50%,var(--chat-border))] text-[var(--chat-accent-strong)]"
                              : "border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                          )}
                        >
                          <Icon size={10} />{m.label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* LCARS */}
          <section>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] mb-3">LCARS</div>
            <div className="grid grid-cols-3 gap-2">
              {LCARS_CARDS.map((card) => {
                const active = theme === card.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => setTheme(card.id as Parameters<typeof setTheme>[0])}
                    className={cn(
                      "flex flex-col items-center gap-2 p-3 rounded-lg border transition-colors text-left",
                      active
                        ? "border-[color:color-mix(in_srgb,var(--chat-accent)_60%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent)_8%,transparent)]"
                        : "border-[var(--chat-border)] bg-[var(--chat-panel)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))]"
                    )}
                  >
                    <MiniPreview card={card} active={active} />
                    <span className="text-[11px] font-medium text-[var(--chat-text)] text-center leading-tight">{card.label}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Extended */}
          <section>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] mb-3">Extended</div>
            <div className="grid grid-cols-2 gap-2">
              {EXTENDED_CARDS.map((card) => {
                const active = theme === card.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => setTheme(card.id as Parameters<typeof setTheme>[0])}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors text-left",
                      active
                        ? "border-[color:color-mix(in_srgb,var(--chat-accent)_60%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent)_8%,transparent)]"
                        : "border-[var(--chat-border)] bg-[var(--chat-panel)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))]"
                    )}
                  >
                    <MiniPreview card={card} active={active} />
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-[var(--chat-text)] truncate">{card.label}</div>
                      <div className="text-[10px] text-[var(--chat-muted)] mt-0.5 truncate">{card.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </div>
  );

  return typeof window !== "undefined" ? createPortal(modal, document.body) : null;
}
