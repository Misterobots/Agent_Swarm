"use client";

import { useEffect, useCallback, useRef } from "react";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";
import { useAccess } from "@/lib/hooks/use-access";
import { PalaceArchitecture } from "./palace-architecture";
import { LobbyView } from "./views/lobby-view";
import { WingView } from "./views/wing-view";
import { RoomView } from "./views/room-view";
import { PalaceHud } from "./palace-hud";
import { MemoryDetailPanel } from "./memory-detail-panel";

export function PalaceViewer() {
  const location = usePalaceStore((s) => s.location);
  const layout = usePalaceStore((s) => s.layout);
  const layoutLoading = usePalaceStore((s) => s.layoutLoading);
  const layoutError = usePalaceStore((s) => s.layoutError);
  const loadLayout = usePalaceStore((s) => s.loadLayout);
  const adminViewingOwner = usePalaceStore((s) => s.adminViewingOwner);
  const setAdminOwner = usePalaceStore((s) => s.setAdminOwner);
  const selectedMemory = usePalaceStore((s) => s.selectedMemory);
  const goBack = usePalaceStore((s) => s.goBack);
  const selectMemory = usePalaceStore((s) => s.selectMemory);
  const roomMemories = usePalaceStore((s) => s.roomMemories);
  const { isAdmin, username, uid, loading: accessLoading } = useAccess();
  const scopeInitialized = useRef(false);

  const colors = usePalaceColors();

  useEffect(() => {
    if (accessLoading) return;

    if (isAdmin && username && !scopeInitialized.current && adminViewingOwner === null) {
      scopeInitialized.current = true;
      setAdminOwner(uid || username);
      return;
    }

    scopeInitialized.current = true;
    loadLayout(adminViewingOwner ?? undefined);
  }, [accessLoading, isAdmin, username, adminViewingOwner, setAdminOwner, loadLayout]);

  // Keyboard shortcuts (unchanged)
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (selectedMemory) {
          selectMemory(null);
        } else if (location.level !== "lobby") {
          goBack();
        }
        return;
      }

      if (
        (e.key === "ArrowLeft" || e.key === "ArrowRight") &&
        (location.level === "hall" || location.level === "room") &&
        roomMemories.length > 0
      ) {
        e.preventDefault();
        const currentIdx = selectedMemory
          ? roomMemories.findIndex((m) => m.id === selectedMemory.id)
          : -1;
        let nextIdx: number;
        if (e.key === "ArrowRight") {
          nextIdx = currentIdx < roomMemories.length - 1 ? currentIdx + 1 : 0;
        } else {
          nextIdx = currentIdx > 0 ? currentIdx - 1 : roomMemories.length - 1;
        }
        selectMemory(roomMemories[nextIdx]);
      }
    },
    [selectedMemory, location.level, goBack, selectMemory, roomMemories],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const activeOwnerScope = adminViewingOwner ?? undefined;

  if (layoutLoading || accessLoading) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div className="flex flex-col items-center gap-3">
          <div
            className="w-10 h-10 border-2 rounded-full animate-spin"
            style={{
              borderColor: "var(--chat-border)",
              borderTopColor: "var(--chat-accent)",
            }}
          />
          <span style={{ color: "var(--chat-muted)" }} className="text-sm">
            Mapping the Palace…
          </span>
        </div>
      </div>
    );
  }

  if (layoutError) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div
          className="flex flex-col items-center gap-3 p-6 rounded-xl max-w-sm text-center"
          style={{ background: "var(--chat-surface)", border: "1px solid var(--chat-border)" }}
        >
          <span style={{ color: "var(--chat-accent-2)" }} className="text-lg font-medium">
            Could not load Palace
          </span>
          <span style={{ color: "var(--chat-muted)" }} className="text-sm">
            {layoutError}
          </span>
          <button
            onClick={() => loadLayout(activeOwnerScope)}
            className="mt-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
            style={{
              background: "var(--chat-accent)",
              color: "var(--chat-bg)",
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Unique key forces re-mount (and fresh CSS enter animation) on navigation
  const sceneKey = `${location.level}-${location.wing ?? ""}-${location.hall ?? ""}-${location.room ?? ""}`;

  return (
    <div className="h-full w-full relative overflow-hidden" style={{ background: colors.bg }}>
      {/* ── Layer 0: Atmospheric gradient background ──────────── */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 50% 55%, ${colors.accent}12 0%, transparent 70%),
            radial-gradient(ellipse 50% 40% at 50% 100%, ${colors.accentStrong}0A 0%, transparent 50%),
            radial-gradient(ellipse 120% 80% at 50% 20%, ${colors.shadow}40 0%, transparent 60%),
            ${colors.bg}
          `,
        }}
      />

      {/* ── Layer 1: Architectural structure (SVG, theme-aware) ── */}
      <PalaceArchitecture />

      {/* ── Layer 2: CSS 3D spatial content ───────────────────── */}
      <div
        className="absolute inset-0 flex items-center justify-center"
        style={{ zIndex: 1, perspective: "1200px", perspectiveOrigin: "50% 45%" }}
      >
        <div
          key={sceneKey}
          style={{
            animation: "palaceSceneEnter 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
          }}
        >
          {location.level === "lobby" && layout && (
            <LobbyView wings={layout.wings} totalMemories={layout.total_memories} />
          )}
          {location.level === "wing" && layout && (
            <WingView
              wingName={location.wing!}
              halls={layout.wings.find((w) => w.name === location.wing)?.halls ?? []}
            />
          )}
          {(location.level === "hall" || location.level === "room") && <RoomView />}
        </div>
      </div>

      {/* ── Layer 3: HUD Overlay ─────────────────────────────── */}
      <PalaceHud />

      {/* ── Layer 4: Memory Detail Panel ─────────────────────── */}
      {selectedMemory && <MemoryDetailPanel />}

      {/* ── Global keyframes ─────────────────────────────────── */}
      <style>{`
        @keyframes palaceSceneEnter {
          from {
            opacity: 0;
            transform: translateY(20px) scale(0.96);
            filter: blur(4px);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
            filter: blur(0px);
          }
        }
        @keyframes palaceCardEnter {
          from {
            opacity: 0;
            transform: translateY(24px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        @keyframes palaceGlowPulse {
          0%, 100% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.05); }
        }
        @keyframes palaceArchFadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
