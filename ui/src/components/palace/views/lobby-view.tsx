"use client";

import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";
import type { WingInfo } from "@/lib/api/palace";

/* ── Wing icon mapping for spatial recognition ─────────────────────── */
const WING_ICONS: Record<string, string> = {
  builder: "🔨",
  navigator: "🧭",
  architect: "📐",
  explorer: "🗺️",
  researcher: "🔬",
  engineer: "⚙️",
  designer: "🎨",
  analyst: "📊",
  operator: "🎛️",
  guardian: "🛡️",
};

function wingIcon(name: string): string {
  const key = name.replace(/^wing_/, "").replace(/_/g, " ").toLowerCase();
  return WING_ICONS[key] ?? "🏛️";
}

interface LobbyViewProps {
  wings: WingInfo[];
  totalMemories: number;
}

export function LobbyView({ wings, totalMemories }: LobbyViewProps) {
  const navigateTo = usePalaceStore((s) => s.navigateTo);
  const colors = usePalaceColors();

  // Light-theme glass overrides
  const glassAlpha = colors.isLight ? 0.6 : 0.32;
  const glassBorderAlpha = colors.isLight ? 0.35 : 0.18;
  const glassShadow = colors.isLight
    ? "0 8px 32px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.06)"
    : "0 8px 32px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.04)";

  return (
    <div className="flex flex-col items-center gap-8 px-6 w-full max-w-5xl">
      {/* Title area */}
      <div
        className="text-center"
        style={{ animation: "palaceCardEnter 0.5s cubic-bezier(0.16, 1, 0.3, 1) both" }}
      >
        {/* Central glow — enhanced orb with inner bloom */}
        <div
          className="mx-auto mb-5 w-24 h-24 rounded-full flex items-center justify-center"
          style={{
            background: colors.isLight
              ? `radial-gradient(circle, ${colors.accent}18 0%, ${colors.accent}06 50%, transparent 100%)`
              : `radial-gradient(circle, ${colors.accent}35 0%, ${colors.accent}12 50%, transparent 100%)`,
            boxShadow: colors.isLight
              ? `0 0 40px ${colors.accent}12`
              : `0 0 80px ${colors.accent}20, 0 0 160px ${colors.accent}0A`,
            animation: "palaceGlowPulse 4s ease-in-out infinite",
          }}
        >
          {/* Inner bloom ring */}
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center"
            style={{
              background: colors.isLight
                ? `radial-gradient(circle, ${colors.accent}20 0%, ${colors.accent}08 60%, transparent 100%)`
                : `radial-gradient(circle, ${colors.accent}60 0%, ${colors.accent}28 50%, transparent 100%)`,
              boxShadow: colors.isLight
                ? `0 0 20px ${colors.accent}15`
                : `0 0 30px ${colors.accent}40, inset 0 0 20px ${colors.accent}18`,
            }}
          >
            {/* Bright core */}
            <div
              className="w-6 h-6 rounded-full"
              style={{
                background: colors.isLight
                  ? `radial-gradient(circle, ${colors.accent}30 0%, transparent 100%)`
                  : `radial-gradient(circle, ${colors.accent}80 0%, ${colors.accent}30 60%, transparent 100%)`,
                boxShadow: colors.isLight
                  ? "none"
                  : `0 0 12px ${colors.accent}50`,
              }}
            />
          </div>
        </div>
        <h2
          className="text-2xl font-light tracking-widest uppercase mb-1.5"
          style={{ color: colors.text }}
        >
          Memory Palace
        </h2>
        <p className="text-sm tracking-wide" style={{ color: colors.muted }}>
          {totalMemories} memor{totalMemories !== 1 ? "ies" : "y"} across {wings.length} wing
          {wings.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Wing portal cards */}
      <div className="flex flex-wrap justify-center gap-5">
        {wings.map((wing, i) => {
          const displayName = wing.name.replace(/^wing_/, "").replace(/_/g, " ");
          const totalDrawers = wing.halls.reduce(
            (sum, h) => h.rooms.reduce((s, r) => s + r.drawer_count, sum),
            0,
          );
          const icon = wingIcon(wing.name);

          return (
            <button
              key={wing.name}
              onClick={() => navigateTo({ level: "wing", wing: wing.name })}
              className="group relative flex flex-col items-start p-6 rounded-2xl cursor-pointer text-left"
              style={{
                width: "280px",
                background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${glassAlpha})`,
                backdropFilter: "blur(24px) saturate(1.3)",
                WebkitBackdropFilter: "blur(24px) saturate(1.3)",
                border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`,
                boxShadow: glassShadow,
                transition:
                  "transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s ease, border-color 0.4s ease",
                animation: `palaceCardEnter 0.55s cubic-bezier(0.16, 1, 0.3, 1) ${0.15 + i * 0.1}s both`,
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget;
                el.style.transform = "translateY(-8px) scale(1.03)";
                el.style.boxShadow = colors.isLight
                  ? `0 20px 60px rgba(0,0,0,0.12), 0 0 30px ${colors.accent}12`
                  : `0 20px 60px rgba(0,0,0,0.25), 0 0 40px ${colors.accent}18`;
                el.style.borderColor = `${colors.accent}45`;
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget;
                el.style.transform = "";
                el.style.boxShadow = glassShadow;
                el.style.borderColor = "";
              }}
            >
              {/* Top accent gradient line */}
              <div
                className="absolute top-0 left-6 right-6 h-px rounded-b"
                style={{
                  background: `linear-gradient(90deg, transparent, ${colors.accent}70, transparent)`,
                }}
              />

              {/* Wing icon — unique per wing */}
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
                style={{
                  background: `${colors.accent}12`,
                  border: `1px solid ${colors.accent}20`,
                  boxShadow: `0 0 16px ${colors.accent}08`,
                }}
              >
                <span className="text-lg" style={{ filter: "drop-shadow(0 0 4px currentColor)" }}>
                  {icon}
                </span>
              </div>

              {/* Wing name */}
              <h3
                className="text-base font-medium capitalize mb-1 tracking-wide"
                style={{ color: colors.text }}
              >
                {displayName}
              </h3>

              {/* Stats */}
              <p className="text-xs mb-5" style={{ color: colors.muted }}>
                {wing.halls.length} hall{wing.halls.length !== 1 ? "s" : ""} ·{" "}
                {totalDrawers} memor{totalDrawers !== 1 ? "ies" : "y"}
              </p>

              {/* Bottom accent */}
              <div
                className="w-full h-px mb-3"
                style={{
                  background: `linear-gradient(90deg, ${colors.accent}30, transparent)`,
                }}
              />

              {/* Enter indicator */}
              <div
                className="flex items-center gap-2 text-xs font-medium"
                style={{ color: colors.accent, opacity: 0.7 }}
              >
                <span className="tracking-wide">Enter wing</span>
                <span className="transition-transform duration-300 group-hover:translate-x-1.5">
                  →
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Decorative floor glow */}
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[700px] h-[250px] pointer-events-none"
        style={{
          background: `radial-gradient(ellipse at center, ${colors.accent}0A 0%, transparent 70%)`,
          animation: "palaceGlowPulse 5s ease-in-out infinite",
        }}
      />
    </div>
  );
}
