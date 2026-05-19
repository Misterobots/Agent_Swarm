"use client";

import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";
import type { HallInfo } from "@/lib/api/palace";

interface WingViewProps {
  wingName: string;
  halls: HallInfo[];
}

export function WingView({ wingName, halls }: WingViewProps) {
  const navigateTo = usePalaceStore((s) => s.navigateTo);
  const colors = usePalaceColors();

  const displayWing = wingName.replace(/^wing_/, "").replace(/_/g, " ");
  const totalRooms = halls.reduce((s, h) => s + h.rooms.length, 0);
  const totalMemories = halls.reduce(
    (s, h) => h.rooms.reduce((rs, r) => rs + r.drawer_count, s),
    0,
  );

  // Light-theme glass overrides
  const glassAlpha = colors.isLight ? 0.55 : 0.28;
  const glassBorderAlpha = colors.isLight ? 0.3 : 0.15;
  const glassShadow = colors.isLight
    ? "0 4px 24px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)"
    : "0 4px 24px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.03)";

  // Flatten halls → rooms for card rendering
  let cardIndex = 0;

  return (
    <div className="flex flex-col items-center gap-6 px-6 w-full max-w-5xl">
      {/* Wing header */}
      <div
        className="text-center"
        style={{
          animation: "palaceCardEnter 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        }}
      >
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] tracking-wide uppercase mb-3"
          style={{
            background: `${colors.accent}12`,
            border: `1px solid ${colors.accent}20`,
            color: colors.accent,
          }}
        >
          <span>🏛️</span>
          <span>{displayWing}</span>
        </div>
        <h2
          className="text-xl font-light tracking-wide capitalize mb-1"
          style={{ color: colors.text }}
        >
          {displayWing}
        </h2>
        <p className="text-sm" style={{ color: colors.muted }}>
          {totalRooms} room{totalRooms !== 1 ? "s" : ""} · {totalMemories} memor
          {totalMemories !== 1 ? "ies" : "y"}
        </p>
      </div>

      {/* Hall sections */}
      {halls.map((hall) => {
        const displayHall = hall.name.replace(/^hall_/, "").replace(/_/g, " ");

        return (
          <div key={hall.name} className="w-full">
            {/* Hall label (only show if >1 hall) */}
            {halls.length > 1 && (
              <div className="flex items-center gap-3 mb-3 px-1">
                <div
                  className="flex-1 h-px"
                  style={{ background: `${colors.border}30` }}
                />
                <span
                  className="text-[11px] tracking-wider uppercase"
                  style={{ color: colors.muted }}
                >
                  {displayHall}
                </span>
                <div
                  className="flex-1 h-px"
                  style={{ background: `${colors.border}30` }}
                />
              </div>
            )}

            {/* Room cards */}
            <div className="flex flex-wrap justify-center gap-4">
              {hall.rooms.map((room) => {
                const displayRoom = room.name.replace(/_/g, " ");
                const delay = 0.1 + cardIndex * 0.07;
                cardIndex++;

                return (
                  <button
                    key={`${hall.name}-${room.name}`}
                    onClick={() =>
                      navigateTo({
                        level: "room",
                        wing: wingName,
                        hall: hall.name,
                        room: room.name,
                      })
                    }
                    className="group relative flex flex-col items-start p-5 rounded-xl cursor-pointer text-left"
                    style={{
                      width: "230px",
                      background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${glassAlpha})`,
                      backdropFilter: "blur(20px) saturate(1.2)",
                      WebkitBackdropFilter: "blur(20px) saturate(1.2)",
                      border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`,
                      boxShadow: glassShadow,
                      transition:
                        "transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s ease, border-color 0.35s ease",
                      animation: `palaceCardEnter 0.45s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s both`,
                    }}
                    onMouseEnter={(e) => {
                      const el = e.currentTarget;
                      el.style.transform = "translateY(-5px) scale(1.02)";
                      el.style.boxShadow = colors.isLight
                        ? `0 14px 44px rgba(0,0,0,0.1), 0 0 28px ${colors.accent}08`
                        : `0 14px 44px rgba(0,0,0,0.18), 0 0 28px ${colors.accent}12`;
                      el.style.borderColor = `${colors.accent}35`;
                    }}
                    onMouseLeave={(e) => {
                      const el = e.currentTarget;
                      el.style.transform = "";
                      el.style.boxShadow = glassShadow;
                      el.style.borderColor = "";
                    }}
                  >
                    {/* Top accent line */}
                    <div
                      className="absolute top-0 left-5 right-5 h-px rounded-b"
                      style={{
                        background: `linear-gradient(90deg, transparent, ${colors.accent}50, transparent)`,
                      }}
                    />

                    {/* Room icon */}
                    <div
                      className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
                      style={{
                        background: `${colors.accent}10`,
                        border: `1px solid ${colors.accent}18`,
                      }}
                    >
                      <span className="text-sm">🚪</span>
                    </div>

                    {/* Room name */}
                    <h3
                      className="text-sm font-medium capitalize mb-1"
                      style={{ color: colors.text }}
                    >
                      {displayRoom}
                    </h3>

                    {/* Drawer count */}
                    <p className="text-xs mb-4" style={{ color: colors.muted }}>
                      {room.drawer_count} memor{room.drawer_count !== 1 ? "ies" : "y"}
                    </p>

                    {/* Enter indicator */}
                    <div
                      className="mt-auto flex items-center gap-1.5 text-xs"
                      style={{ color: colors.accent, opacity: 0.6 }}
                    >
                      <span className="tracking-wide">Open</span>
                      <span className="transition-transform duration-300 group-hover:translate-x-1">
                        →
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
