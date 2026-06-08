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
  | "cyberpunk"
  // Extended themes (Claude Design v1)
  | "shadowrun"
  | "ops"
  | "terminal"
  | "hal9000"
  | "nostromo"
  | "tron"
  | "bladerunner"
  | "dune"
  | "memex-archive"
  // Legacy (migration only — no CSS, coerce to "memex")
  | "amber"
  | "ember" | "slate" | "signal" | "office"
  | "hacker" | "star-trek" | "minimal";

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
  workshopMode: boolean;
  groundingWeb: boolean;
  groundingDocs: boolean;
  groundingFile: boolean;
  // Quality/Effort settings (overall)
  solvingMaxIter: number; // MarsRL max iterations (0 = unlimited)
  solvingMaxTime: number; // MarsRL max time in seconds (0 = unlimited)
  // Developer-mode granular per-agent budgets. 0 = no per-call cap (fall back to overall).
  solvingSolverNDrafts: number;       // Best-of-N solver drafts (1–3 in UI, 1 = single pass)
  solvingSolverMaxTime: number;       // Per-call solver wall-clock (seconds, 0 = none)
  solvingVerifierNRuns: number;       // N-way verifier consensus (1 = single pass, 1–5 in UI)
  solvingVerifierMaxTime: number;     // Per-call verifier wall-clock (seconds, 0 = none)
  solvingCorrectorNPasses: number;    // N sequential corrector passes per round (1–3 in UI)
  solvingCorrectorMaxTime: number;    // Per-call corrector wall-clock (seconds, 0 = none)
  // Agent transparency — controls what internal agent activity is visible
  // "off": hidden entirely; "status": collapsed trace after response; "full": live-expanding during stream
  agentTransparency: "off" | "status" | "full";
  setAgentTransparency: (level: "off" | "status" | "full") => void;

  // Layout
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  sidebarSlim: boolean;
  setSidebarSlim: (slim: boolean) => void;
  navLayout: "sidebar" | "topbar";
  setNavLayout: (layout: "sidebar" | "topbar") => void;
  soundEnabled: boolean;
  setSoundEnabled: (enabled: boolean) => void;
  themePickerMode: "popover" | "gallery";
  setThemePickerMode: (mode: "popover" | "gallery") => void;
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
  setWorkshopMode: (on: boolean) => void;
  /** Pre-fills the chat input; cleared by ChatInput after consumption */
  pendingInput: string;
  setPendingInput: (text: string) => void;
  setGroundingWeb: (on: boolean) => void;
  setGroundingDocs: (on: boolean) => void;
  setGroundingFile: (on: boolean) => void;
  setSolvingMaxIter: (iter: number) => void;
  setSolvingMaxTime: (time: number) => void;
  setSolvingSolverNDrafts: (n: number) => void;
  setSolvingSolverMaxTime: (time: number) => void;
  setSolvingVerifierNRuns: (n: number) => void;
  setSolvingVerifierMaxTime: (time: number) => void;
  setSolvingCorrectorNPasses: (n: number) => void;
  setSolvingCorrectorMaxTime: (time: number) => void;
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
      workshopMode: false,
      groundingWeb: false,
      groundingDocs: false,
      groundingFile: false,
      solvingMaxIter: 2, // Default: 2 iterations
      solvingMaxTime: 0, // Default: no time limit
      solvingSolverNDrafts: 1,      // Default: single pass (no best-of-N)
      solvingSolverMaxTime: 0,      // Default: no per-call cap
      solvingVerifierNRuns: 1,      // Default: single verifier run
      solvingVerifierMaxTime: 0,
      solvingCorrectorNPasses: 1,   // Default: single corrector pass
      solvingCorrectorMaxTime: 0,
      agentTransparency: "status",
      setAgentTransparency: (agentTransparency) => set({ agentTransparency }),
      sidebarOpen: true,
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      sidebarSlim: false,
      setSidebarSlim: (sidebarSlim) => set({ sidebarSlim }),
      soundEnabled: true,
      setSoundEnabled: (soundEnabled) => set({ soundEnabled }),
      navLayout: "sidebar",
      setNavLayout: (navLayout) => set({ navLayout }),
      themePickerMode: "popover",
      setThemePickerMode: (themePickerMode) => set({ themePickerMode }),
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
      setWorkshopMode: (workshopMode) => set({ workshopMode }),
      pendingInput: "",
      setPendingInput: (pendingInput) => set({ pendingInput }),
      setGroundingWeb: (groundingWeb) => set({ groundingWeb }),
      setGroundingDocs: (groundingDocs) => set({ groundingDocs }),
      setGroundingFile: (groundingFile) => set({ groundingFile }),
      setSolvingMaxIter: (solvingMaxIter) => set({ solvingMaxIter }),
      setSolvingMaxTime: (solvingMaxTime) => set({ solvingMaxTime }),
      setSolvingSolverNDrafts: (solvingSolverNDrafts) => set({ solvingSolverNDrafts }),
      setSolvingSolverMaxTime: (solvingSolverMaxTime) => set({ solvingSolverMaxTime }),
      setSolvingVerifierNRuns: (solvingVerifierNRuns) => set({ solvingVerifierNRuns }),
      setSolvingVerifierMaxTime: (solvingVerifierMaxTime) => set({ solvingVerifierMaxTime }),
      setSolvingCorrectorNPasses: (solvingCorrectorNPasses) => set({ solvingCorrectorNPasses }),
      setSolvingCorrectorMaxTime: (solvingCorrectorMaxTime) => set({ solvingCorrectorMaxTime }),
    }),
    {
      name: "memex-settings",
      version: 8,
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
        // v3 -> v4: introduce granular per-agent quality budgets.
        if (fromVersion < 4) {
          if (state.solvingSolverNDrafts === undefined) state.solvingSolverNDrafts = 1;
          if (state.solvingSolverMaxTime === undefined) state.solvingSolverMaxTime = 0;
          if (state.solvingVerifierMaxTime === undefined) state.solvingVerifierMaxTime = 0;
          if (state.solvingCorrectorMaxTime === undefined) state.solvingCorrectorMaxTime = 0;
        }
        // v4 -> v5: add per-agent iteration counts (verifier consensus runs, corrector passes).
        if (fromVersion < 5) {
          if (state.solvingVerifierNRuns === undefined) state.solvingVerifierNRuns = 1;
          if (state.solvingCorrectorNPasses === undefined) state.solvingCorrectorNPasses = 1;
        }
        // v5 -> v6: add navLayout and themePickerMode.
        if (fromVersion < 6) {
          if ((state as any).navLayout === undefined) (state as any).navLayout = "sidebar";
          if ((state as any).themePickerMode === undefined) (state as any).themePickerMode = "popover";
        }
        // v6 -> v7: add soundEnabled
        if (fromVersion < 7) {
          if ((state as any).soundEnabled === undefined) (state as any).soundEnabled = true;
        }
        // v7 -> v8: add agentTransparency
        if (fromVersion < 8) {
          if ((state as any).agentTransparency === undefined) (state as any).agentTransparency = "status";
        }
        return state as SettingsState;
      },
    }
  )
);
