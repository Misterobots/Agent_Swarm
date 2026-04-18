"use client";

import { useCallback, useState } from "react";
import { ChevronRight, Search, ArrowLeft, Users } from "lucide-react";
import { usePalaceStore, type PalaceLocation } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";
import { useAccess } from "@/lib/hooks/use-access";

export function PalaceHud() {
  const location = usePalaceStore((s) => s.location);
  const locationHistory = usePalaceStore((s) => s.locationHistory);
  const navigateTo = usePalaceStore((s) => s.navigateTo);
  const goBack = usePalaceStore((s) => s.goBack);
  const layout = usePalaceStore((s) => s.layout);
  const performSearch = usePalaceStore((s) => s.performSearch);
  const clearSearch = usePalaceStore((s) => s.clearSearch);
  const searchResults = usePalaceStore((s) => s.searchResults);
  const adminViewingOwner = usePalaceStore((s) => s.adminViewingOwner);
  const setAdminOwner = usePalaceStore((s) => s.setAdminOwner);
  const loadLayout = usePalaceStore((s) => s.loadLayout);
  const { isAdmin } = useAccess();
  const colors = usePalaceColors();

  // Light-theme glass overrides
  const glassAlpha = colors.isLight ? 0.7 : 0.6;
  const glassBgBack = colors.isLight ? 0.75 : 0.65;
  const glassBorderAlpha = colors.isLight ? 0.35 : 0.25;
  const glassShadow = colors.isLight
    ? "0 2px 12px rgba(0,0,0,0.06)"
    : "0 2px 16px rgba(0,0,0,0.12)";

  const [searchValue, setSearchValue] = useState("");
  const [showOwnerInput, setShowOwnerInput] = useState(false);
  const [ownerInput, setOwnerInput] = useState("");

  // ── Breadcrumb segments ───────────────────────────────────────────────

  const breadcrumbs: { label: string; loc: PalaceLocation }[] = [
    { label: "Palace", loc: { level: "lobby" } },
  ];

  if (location.wing) {
    const displayWing = location.wing.replace(/^wing_/, "").replace(/_/g, " ");
    breadcrumbs.push({ label: displayWing, loc: { level: "wing", wing: location.wing } });
  }
  if (location.hall) {
    const displayHall = location.hall.replace(/^hall_/, "").replace(/_/g, " ");
    breadcrumbs.push({
      label: displayHall,
      loc: { level: "hall", wing: location.wing, hall: location.hall },
    });
  }
  if (location.room) {
    breadcrumbs.push({
      label: location.room.replace(/_/g, " "),
      loc: { level: "room", wing: location.wing, hall: location.hall, room: location.room },
    });
  }

  const handleSearch = useCallback(() => {
    if (searchValue.trim()) {
      performSearch(searchValue.trim(), adminViewingOwner ?? undefined);
    } else {
      clearSearch();
    }
  }, [searchValue, performSearch, clearSearch, adminViewingOwner]);

  const handleSearchKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleSearch();
      if (e.key === "Escape") {
        setSearchValue("");
        clearSearch();
      }
    },
    [handleSearch, clearSearch],
  );

  const handleOwnerSwitch = useCallback(() => {
    const oid = ownerInput.trim() || null;
    setAdminOwner(oid);
    loadLayout(oid ?? undefined);
    setShowOwnerInput(false);
  }, [ownerInput, setAdminOwner, loadLayout]);

  return (
    <div className="absolute inset-x-0 top-0 pointer-events-none z-10">
      {/* Top bar */}
      <div className="flex items-center justify-between p-3 pointer-events-auto">
        {/* Left: Back + Breadcrumbs */}
        <div className="flex items-center gap-2">
          {location.level !== "lobby" && (
            <button
              onClick={goBack}
              className="flex items-center justify-center w-8 h-8 rounded-lg transition-all hover:scale-105"
              style={{
                background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${glassBgBack})`,
                backdropFilter: "blur(16px) saturate(1.4)",
                WebkitBackdropFilter: "blur(16px) saturate(1.4)",
                border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`,
                color: "var(--chat-text)",
                boxShadow: glassShadow,
              }}
              title="Go back (Esc)"
            >
              <ArrowLeft size={16} />
            </button>
          )}

          <div
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm"
            style={{
              background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${glassAlpha})`,
              backdropFilter: "blur(16px) saturate(1.4)",
              WebkitBackdropFilter: "blur(16px) saturate(1.4)",
              border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`,
              boxShadow: glassShadow,
            }}
          >
            {breadcrumbs.map((crumb, i) => (
              <span key={crumb.label} className="flex items-center gap-1">
                {i > 0 && <ChevronRight size={12} style={{ color: "var(--chat-muted)" }} />}
                <button
                  onClick={() => {
                    if (i < breadcrumbs.length - 1) {
                      navigateTo(crumb.loc);
                    }
                  }}
                  className="transition-colors hover:underline relative"
                  style={{
                    color:
                      i === breadcrumbs.length - 1
                        ? "var(--chat-accent)"
                        : "var(--chat-muted)",
                    fontWeight: i === breadcrumbs.length - 1 ? 600 : 400,
                    cursor: i < breadcrumbs.length - 1 ? "pointer" : "default",
                  }}
                >
                  {crumb.label}
                  {/* Active crumb underline indicator */}
                  {i === breadcrumbs.length - 1 && (
                    <span
                      className="absolute -bottom-0.5 left-0 right-0 h-[2px] rounded-full"
                      style={{ background: "var(--chat-accent)", opacity: 0.5 }}
                    />
                  )}
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Right: Search + Admin wing switch */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <div
            className="flex items-center rounded-lg overflow-hidden"
            style={{
              background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${glassAlpha})`,
              backdropFilter: "blur(16px) saturate(1.4)",
              WebkitBackdropFilter: "blur(16px) saturate(1.4)",
              border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`,
              boxShadow: glassShadow,
            }}
          >
            <Search size={14} className="ml-2" style={{ color: "var(--chat-muted)" }} />
            <input
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={handleSearchKey}
              placeholder="Search memories…"
              className="bg-transparent border-none outline-none px-2 py-1.5 text-sm w-44"
              style={{ color: "var(--chat-text)" }}
            />
          </div>

          {/* Admin wing switch */}
          {isAdmin && (
            <div className="relative">
              <button
                onClick={() => setShowOwnerInput(!showOwnerInput)}
                className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs transition-colors"
                style={{
                  background: adminViewingOwner
                    ? "var(--chat-accent)"
                    : "var(--chat-surface)",
                  color: adminViewingOwner
                    ? "var(--chat-bg)"
                    : "var(--chat-muted)",
                  border: "1px solid var(--chat-border)",
                }}
                title="Switch user scope (admin)"
              >
                <Users size={14} />
                {adminViewingOwner ? adminViewingOwner : "All users"}
              </button>

              {showOwnerInput && (
                <div
                  className="absolute right-0 top-full mt-1 p-2 rounded-lg flex gap-1"
                  style={{
                    background: "var(--chat-surface)",
                    border: "1px solid var(--chat-border)",
                    minWidth: 200,
                  }}
                >
                  <input
                    value={ownerInput}
                    onChange={(e) => setOwnerInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleOwnerSwitch()}
                    placeholder="owner_id (blank=all)"
                    className="bg-transparent border-none outline-none text-sm flex-1 px-1"
                    style={{ color: "var(--chat-text)" }}
                    autoFocus
                  />
                  <button
                    onClick={handleOwnerSwitch}
                    className="px-2 py-0.5 rounded text-xs font-medium"
                    style={{
                      background: "var(--chat-accent)",
                      color: "var(--chat-bg)",
                    }}
                  >
                    Go
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Search results toast */}
      {searchResults && (
        <div className="mx-3 pointer-events-auto">
          <div
            className="px-3 py-2 rounded-lg text-sm flex items-center justify-between"
            style={{
              background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${glassBgBack})`,
              backdropFilter: "blur(16px) saturate(1.4)",
              WebkitBackdropFilter: "blur(16px) saturate(1.4)",
              border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${glassBorderAlpha})`,
              color: "var(--chat-text)",
              boxShadow: glassShadow,
            }}
          >
            <span>
              Found <strong>{searchResults.length}</strong> matching memories
              {searchResults.length > 0 && location.level !== "room" && (
                <span style={{ color: "var(--chat-muted)" }}>
                  {" "}— navigate to a room to see highlighted drawers
                </span>
              )}
            </span>
            <button
              onClick={() => {
                setSearchValue("");
                clearSearch();
              }}
              className="ml-3 text-xs underline"
              style={{ color: "var(--chat-muted)" }}
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Total memories badge (lobby only) */}
      {location.level === "lobby" && layout && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 pointer-events-none">
          <div
            className="px-4 py-2 rounded-full text-sm"
            style={{
              background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${colors.isLight ? 0.65 : 0.55})`,
              backdropFilter: "blur(16px) saturate(1.4)",
              WebkitBackdropFilter: "blur(16px) saturate(1.4)",
              border: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${colors.isLight ? 0.3 : 0.2})`,
              color: "var(--chat-muted)",
              boxShadow: colors.isLight
                ? "0 4px 16px rgba(0,0,0,0.06)"
                : "0 4px 20px rgba(0,0,0,0.15)",
            }}
          >
            {layout.total_memories} memories across {layout.wings.length} wings
          </div>
        </div>
      )}
    </div>
  );
}
