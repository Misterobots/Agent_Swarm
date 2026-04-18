import { create } from "zustand";
import type { PalaceLayout, MemoryItem, AuditEntry } from "@/lib/api/palace";
import {
  fetchPalaceLayout,
  fetchRoomMemories,
  searchMemories,
  fetchAuditLog,
} from "@/lib/api/palace";

// ── Location hierarchy ────────────────────────────────────────────────────

export type PalaceLevel = "lobby" | "wing" | "hall" | "room";

export interface PalaceLocation {
  level: PalaceLevel;
  wing?: string;
  hall?: string;
  room?: string;
}

// ── Store ─────────────────────────────────────────────────────────────────

interface PalaceState {
  // Navigation
  location: PalaceLocation;
  locationHistory: PalaceLocation[];
  isTransitioning: boolean;

  // Data
  layout: PalaceLayout | null;
  layoutLoading: boolean;
  layoutError: string | null;
  roomMemories: MemoryItem[];
  roomLoading: boolean;

  // Memory detail
  selectedMemory: MemoryItem | null;
  auditLog: AuditEntry[];
  auditLoading: boolean;

  // Search
  searchResults: MemoryItem[] | null;
  searchQuery: string;
  highlightedMemoryIds: Set<string>;

  // Admin scope
  adminViewingOwner: string | null;

  // Actions
  loadLayout: (ownerId?: string) => Promise<void>;
  navigateTo: (loc: PalaceLocation) => void;
  goBack: () => void;
  loadRoomMemories: (wing: string, hall: string, room: string, ownerId?: string) => Promise<void>;
  selectMemory: (mem: MemoryItem | null) => void;
  loadAuditLog: (memoryId: string) => Promise<void>;
  setTransitioning: (v: boolean) => void;
  setAdminOwner: (ownerId: string | null) => void;
  performSearch: (query: string, ownerId?: string) => Promise<void>;
  clearSearch: () => void;
  refreshRoom: () => Promise<void>;
}

export const usePalaceStore = create<PalaceState>()((set, get) => ({
  // Initial state
  location: { level: "lobby" },
  locationHistory: [],
  isTransitioning: false,

  layout: null,
  layoutLoading: false,
  layoutError: null,
  roomMemories: [],
  roomLoading: false,

  selectedMemory: null,
  auditLog: [],
  auditLoading: false,

  searchResults: null,
  searchQuery: "",
  highlightedMemoryIds: new Set(),

  adminViewingOwner: null,

  // ── Actions ───────────────────────────────────────────────────────────

  loadLayout: async (ownerId) => {
    set({ layoutLoading: true, layoutError: null });
    try {
      const layout = await fetchPalaceLayout(ownerId);
      set({ layout, layoutLoading: false });
    } catch (err) {
      set({ layoutError: (err as Error).message, layoutLoading: false });
    }
  },

  navigateTo: (loc) => {
    const { location, locationHistory } = get();
    set({
      locationHistory: [...locationHistory, location],
      location: loc,
      isTransitioning: true,
      selectedMemory: null,
      searchResults: null,
      searchQuery: "",
      highlightedMemoryIds: new Set(),
    });
  },

  goBack: () => {
    const { locationHistory } = get();
    if (locationHistory.length === 0) return;
    const prev = locationHistory[locationHistory.length - 1];
    set({
      location: prev,
      locationHistory: locationHistory.slice(0, -1),
      isTransitioning: true,
      selectedMemory: null,
    });
  },

  loadRoomMemories: async (wing, hall, room, ownerId) => {
    set({ roomLoading: true });
    try {
      const roomMemories = await fetchRoomMemories(wing, hall, room, ownerId);
      set({ roomMemories, roomLoading: false });
    } catch {
      set({ roomMemories: [], roomLoading: false });
    }
  },

  selectMemory: (mem) => set({ selectedMemory: mem }),

  loadAuditLog: async (memoryId) => {
    set({ auditLoading: true });
    try {
      const auditLog = await fetchAuditLog(memoryId);
      set({ auditLog, auditLoading: false });
    } catch {
      set({ auditLog: [], auditLoading: false });
    }
  },

  setTransitioning: (v) => set({ isTransitioning: v }),

  setAdminOwner: (ownerId) => set({ adminViewingOwner: ownerId }),

  performSearch: async (query, ownerId) => {
    if (!query.trim()) {
      set({ searchResults: null, searchQuery: "", highlightedMemoryIds: new Set() });
      return;
    }
    set({ searchQuery: query });
    try {
      const results = await searchMemories(query, ownerId, 20);
      set({
        searchResults: results,
        highlightedMemoryIds: new Set(results.map((r) => r.id)),
      });
    } catch {
      set({ searchResults: [], highlightedMemoryIds: new Set() });
    }
  },

  clearSearch: () =>
    set({ searchResults: null, searchQuery: "", highlightedMemoryIds: new Set() }),

  refreshRoom: async () => {
    const { location, adminViewingOwner } = get();
    if (location.level === "room" && location.wing && location.hall && location.room) {
      await get().loadRoomMemories(
        location.wing,
        location.hall,
        location.room,
        adminViewingOwner ?? undefined,
      );
    }
  },
}));
