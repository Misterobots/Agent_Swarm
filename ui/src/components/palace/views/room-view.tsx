"use client";

import { useEffect } from "react";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";
import { useAccess } from "@/lib/hooks/use-access";

/* ── Visual encoding helpers ──────────────────────────────────────────── */

const TYPE_ICON: Record<string, string> = {
  conversation: "💬",
  code: "⟨⟩",
  error: "⚠️",
  decision: "◆",
  task: "☐",
  semantic: "🧠",
  episodic: "📖",
  procedural: "⚙️",
  preference: "⭐",
  discovery: "🔍",
  general: "◎",
};

function domainHue(domain: string | null): number {
  if (!domain) return 0;
  let hash = 0;
  for (let i = 0; i < domain.length; i++) {
    hash = domain.charCodeAt(i) + ((hash << 5) - hash);
  }
  return ((hash % 360) + 360) % 360;
}

function ageFactor(createdAt: string): number {
  const ageMs = Date.now() - new Date(createdAt).getTime();
  return Math.min(ageMs / (1000 * 60 * 60 * 24 * 30), 1);
}

/* ── Component ────────────────────────────────────────────────────────── */

export function RoomView() {
  const location = usePalaceStore((s) => s.location);
  const roomMemories = usePalaceStore((s) => s.roomMemories);
  const roomLoading = usePalaceStore((s) => s.roomLoading);
  const loadRoomMemories = usePalaceStore((s) => s.loadRoomMemories);
  const selectMemory = usePalaceStore((s) => s.selectMemory);
  const selectedMemory = usePalaceStore((s) => s.selectedMemory);
  const highlightedIds = usePalaceStore((s) => s.highlightedMemoryIds);
  const searchResults = usePalaceStore((s) => s.searchResults);
  const adminViewingOwner = usePalaceStore((s) => s.adminViewingOwner);
  const { username } = useAccess();
  const colors = usePalaceColors();

  useEffect(() => {
    if (location.wing && location.hall && location.room) {
      loadRoomMemories(
        location.wing,
        location.hall,
        location.room,
        adminViewingOwner ?? undefined,
      );
    }
  }, [location.wing, location.hall, location.room, loadRoomMemories, adminViewingOwner]);

  const displayRoom = location.room?.replace(/_/g, " ") ?? "Room";
  const showOwnerBadge = adminViewingOwner === null;
  const scopeSummary = adminViewingOwner
    ? adminViewingOwner === username
      ? "Showing your memories"
      : `Showing memories for ${adminViewingOwner}`
    : "Showing memories from everyone";

  // Light-theme glass overrides
  const glassAlphaBase = colors.isLight ? 0.55 : 0.25;
  const glassAlphaSelected = colors.isLight ? 0.75 : 0.5;
  const glassBorderAlpha = colors.isLight ? 0.3 : 0.12;
  const domainLightness = colors.isLight ? 40 : 65;
  const domainBgLightness = colors.isLight ? 50 : 50;
  const domainBgAlpha = colors.isLight ? 0.08 : 0.12;

  if (roomLoading) {
    return (
      <div className="flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div
            className="w-8 h-8 border-2 rounded-full animate-spin"
            style={{
              borderColor: "var(--chat-border)",
              borderTopColor: "var(--chat-accent)",
            }}
          />
          <span className="text-xs" style={{ color: colors.muted }}>
            Loading memories…
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col items-center gap-5 px-6 w-full max-w-6xl"
      style={{
        maxHeight: "80vh",
        overflowY: "auto",
        scrollbarWidth: "thin",
        scrollbarColor: `${colors.border} transparent`,
      }}
    >
      {/* Room header */}
      <div
        className="text-center shrink-0"
        style={{
          animation: "palaceCardEnter 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        }}
      >
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] tracking-wide uppercase mb-3"
          style={{
            background: `${colors.accent}10`,
            border: `1px solid ${colors.accent}18`,
            color: colors.accent,
          }}
        >
          <span>📂</span>
          <span>{displayRoom}</span>
        </div>
        <h2
          className="text-lg font-light tracking-wide capitalize mb-0.5"
          style={{ color: colors.text }}
        >
          {displayRoom}
        </h2>
        <p className="text-xs" style={{ color: colors.muted }}>
          {roomMemories.length} memor{roomMemories.length !== 1 ? "ies" : "y"}
        </p>
        <p className="text-[11px] mt-1" style={{ color: colors.muted }}>
          {scopeSummary}
        </p>
      </div>

      {/* Empty state */}
      {roomMemories.length === 0 ? (
        <div
          className="text-center py-16"
          style={{
            animation: "palaceCardEnter 0.5s ease both 0.2s",
          }}
        >
          <div className="text-3xl mb-3 opacity-30">📭</div>
          <p className="text-sm" style={{ color: colors.muted }}>
            No memories in this room yet.
          </p>
        </div>
      ) : (
        /* Memory card grid */
        <div
          className="grid gap-3 w-full shrink-0 pb-4"
          style={{
            gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
          }}
        >
          {roomMemories.map((memory, i) => {
            const isHighlighted = !searchResults || highlightedIds.has(memory.id);
            const isSelected = selectedMemory?.id === memory.id;
            const age = ageFactor(memory.created_at);
            const hue = domainHue(memory.domain);
            const icon = TYPE_ICON[memory.memory_type] ?? TYPE_ICON.general;
            const accessPct = Math.min(memory.access_count / 20, 1);

            // Staggered cascade entrance — 60ms between each card
            const staggerDelay = 0.08 + i * 0.06;

            return (
              <button
                key={memory.id}
                onClick={() => selectMemory(memory)}
                className="group relative flex flex-col items-start p-4 rounded-xl cursor-pointer text-left"
                style={{
                  background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${isSelected ? glassAlphaSelected : glassAlphaBase})`,
                  backdropFilter: `blur(${isHighlighted ? 20 : 8}px) saturate(${isHighlighted ? 1.2 : 0.8})`,
                  WebkitBackdropFilter: `blur(${isHighlighted ? 20 : 8}px) saturate(${isHighlighted ? 1.2 : 0.8})`,
                  border: `1px solid ${
                    isSelected
                      ? colors.accent + "55"
                      : `rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`
                  }`,
                  boxShadow: isSelected
                    ? `0 0 28px ${colors.accent}18, 0 4px 20px rgba(0,0,0,${colors.isLight ? 0.08 : 0.15})`
                    : `0 2px 16px rgba(0,0,0,${colors.isLight ? 0.04 : 0.06})`,
                  opacity: isHighlighted ? 1 : 0.3,
                  transition: "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
                  animation: `palaceCardEnter 0.4s cubic-bezier(0.16, 1, 0.3, 1) ${staggerDelay}s both`,
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.transform = "translateY(-3px) scale(1.015)";
                    e.currentTarget.style.borderColor = `hsla(${hue}, 55%, 50%, 0.28)`;
                    e.currentTarget.style.boxShadow = `0 10px 36px rgba(0,0,0,${colors.isLight ? 0.08 : 0.14}), 0 0 24px hsla(${hue}, 55%, 50%, 0.08)`;
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.transform = "";
                    e.currentTarget.style.borderColor = "";
                    e.currentTarget.style.boxShadow = "";
                  }
                }}
              >
                {/* Domain accent bar at top */}
                <div
                  className="absolute top-0 left-4 right-4 h-[1.5px] rounded-b"
                  style={{
                    background: `linear-gradient(90deg, transparent, hsla(${hue}, 55%, 55%, ${0.5 + accessPct * 0.3}), transparent)`,
                  }}
                />

                {/* Header row: icon + type + domain badge */}
                <div className="flex items-start gap-2 mb-2.5 w-full">
                  <span className="text-sm leading-none mt-0.5">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className="text-[11px] font-medium capitalize"
                        style={{ color: colors.text, opacity: 0.75 }}
                      >
                        {memory.memory_type}
                      </span>
                      {showOwnerBadge && memory.owner_id && (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-md font-medium"
                          style={{
                            background: colors.isLight
                              ? "rgba(0, 0, 0, 0.045)"
                              : "rgba(255, 255, 255, 0.06)",
                            color: colors.muted,
                            border: `1px solid ${colors.border}`,
                          }}
                        >
                          {memory.owner_id}
                        </span>
                      )}
                    </div>
                  </div>
                  {memory.domain && (
                    <span
                      className="ml-auto text-[10px] px-1.5 py-0.5 rounded-md font-medium"
                      style={{
                        background: `hsla(${hue}, 45%, ${domainBgLightness}%, ${domainBgAlpha})`,
                        color: `hsla(${hue}, 55%, ${domainLightness}%, 1)`,
                        border: colors.isLight ? `1px solid hsla(${hue}, 40%, 70%, 0.2)` : "none",
                      }}
                    >
                      {memory.domain}
                    </span>
                  )}
                </div>

                {/* Content preview */}
                <p
                  className="text-xs leading-relaxed mb-3"
                  style={{
                    color: colors.text,
                    opacity: 0.65 - age * 0.12,
                    display: "-webkit-box",
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {memory.content}
                </p>

                {/* Footer: access bar + count */}
                <div className="flex items-center gap-2 mt-auto w-full">
                  <div
                    className="flex-1 h-[3px] rounded-full overflow-hidden"
                    style={{
                      background: `rgba(var(--chat-border-rgb, 60, 60, 60), ${colors.isLight ? 0.2 : 0.15})`,
                    }}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.max(accessPct * 100, 6)}%`,
                        background: `hsla(${hue}, 50%, ${colors.isLight ? 45 : 55}%, ${colors.isLight ? 0.7 : 0.6})`,
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>
                  <span className="text-[10px] tabular-nums" style={{ color: colors.muted }}>
                    {memory.access_count}×
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
