import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Skill, Style } from "@/types/chat";

/**
 * The retired 8-theme set is still typed for legacy migration. New installs
 * land on "memex"; old persisted values get migrated to "memex" on load.
 */
export type ChatTheme =
  | "memex"
  | "lcars"
  | "lcars-blue"
  | "lcars-teal"
  | "amber"
  | "ember" | "slate" | "signal" | "office"
  | "hacker" | "star-trek" | "cyberpunk" | "minimal";

export type ThemeMode = "system" | "dark" | "light";

interface SettingsState {
  mode: "standard" | "developer";
  model: string;
  theme: ChatTheme;
  themeMode: ThemeMode;
  skill: Skill;
  style: Style;
  researchMode: boolean;
  ultraplanMode: boolean;
  ultrathinkMode: boolean;
  autoFeedPlan: boolean;
  swarmMode: boolean;
  designMode: boolean;
  groundingWeb: boolean;
  groundingDocs: boolean;
  groundingFile: boolean;
  // Quality/Effort settings
  solvingMaxIter: number; // MarsRL max iterations (0 = unlimited)
  solvingMaxTime: number; // MarsRL max time in seconds (0 = unlimited)
  // Layout
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  setMode: (mode: "standard" | "developer") => void;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
  setThemeMode: (mode: ThemeMode) => void;
  setSkill: (skill: Skill) => void;
  setStyle: (style: Style) => void;
  setResearchMode: (on: boolean) => void;
  setUltraplanMode: (on: boolean) => void;
  setUltrathinkMode: (on: boolean) => void;
  setAutoFeedPlan: (on: boolean) => void;
  setSwarmMode: (on: boolean) => void;
  setDesignMode: (on: boolean) => void;
  setGroundingWeb: (on: boolean) => void;
  setGroundingDocs: (on: boolean) => void;
  setGroundingFile: (on: boolean) => void;
  setSolvingMaxIter: (iter: number) => void;
  setSolvingMaxTime: (time: number) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      mode: "standard",
      model: "Home-AI-Swarm",
      theme: "memex",
      themeMode: "system",
      skill: "general",
      style: "default",
      researchMode: false,
      ultraplanMode: false,
      ultrathinkMode: false,
      autoFeedPlan: false,
      swarmMode: false,
      designMode: false,
      groundingWeb: false,
      groundingDocs: false,
      groundingFile: false,
      solvingMaxIter: 2, // Default: 2 iterations
      solvingMaxTime: 0, // Default: no time limit
      sidebarOpen: true,
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      setMode: (mode) => set({ mode }),
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
      setThemeMode: (themeMode) => set({ themeMode }),
      setSkill: (skill) => set({ skill }),
      setStyle: (style) => set({ style }),
      setResearchMode: (researchMode) => set({ researchMode }),
      setUltraplanMode: (ultraplanMode) => set({ ultraplanMode }),
      setUltrathinkMode: (ultrathinkMode) => set({ ultrathinkMode }),
      setAutoFeedPlan: (autoFeedPlan) => set({ autoFeedPlan }),
      setSwarmMode: (swarmMode) => set({ swarmMode }),
      setDesignMode: (designMode) => set({ designMode }),
      setGroundingWeb: (groundingWeb) => set({ groundingWeb }),
      setGroundingDocs: (groundingDocs) => set({ groundingDocs }),
      setGroundingFile: (groundingFile) => set({ groundingFile }),
      setSolvingMaxIter: (solvingMaxIter) => set({ solvingMaxIter }),
      setSolvingMaxTime: (solvingMaxTime) => set({ solvingMaxTime }),
    }),
    {
      name: "hive-settings",
      version: 3,
      migrate: (persisted: unknown, fromVersion: number) => {
        const state = (persisted ?? {}) as Partial<SettingsState>;
        // v1 -> v3: retired the 8 hand-curated themes plus the warm-amber
        // Memex v1 in favour of a neutral Memex with light/dark/system modes.
        // Anyone with a legacy theme is moved to "memex" w/ system mode.
        if (fromVersion < 3) {
          const previous = state.theme as ChatTheme | undefined;
          if (previous && previous !== "memex") {
            state.theme = "memex";
          }
          if (!state.themeMode) state.themeMode = "system";
        }
        return state as SettingsState;
      },
    }
  )
);
