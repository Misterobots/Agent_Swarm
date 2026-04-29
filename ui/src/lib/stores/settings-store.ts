import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Skill, Style } from "@/types/chat";

export type ChatTheme = "ember" | "slate" | "signal" | "office" | "hacker" | "star-trek" | "cyberpunk" | "minimal";

interface SettingsState {
  mode: "standard" | "developer";
  model: string;
  theme: ChatTheme;
  skill: Skill;
  style: Style;
  researchMode: boolean;
  ultraplanMode: boolean;
  ultrathinkMode: boolean;
  autoFeedPlan: boolean;
  swarmMode: boolean;
  groundingWeb: boolean;
  groundingDocs: boolean;
  groundingFile: boolean;
  // Quality/Effort settings
  solvingMaxIter: number; // MarsRL max iterations (0 = unlimited)
  solvingMaxTime: number; // MarsRL max time in seconds (0 = unlimited)
  setMode: (mode: "standard" | "developer") => void;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
  setSkill: (skill: Skill) => void;
  setStyle: (style: Style) => void;
  setResearchMode: (on: boolean) => void;
  setUltraplanMode: (on: boolean) => void;
  setUltrathinkMode: (on: boolean) => void;
  setAutoFeedPlan: (on: boolean) => void;
  setSwarmMode: (on: boolean) => void;
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
      theme: "ember",
      skill: "general",
      style: "default",
      researchMode: false,
      ultraplanMode: false,
      ultrathinkMode: false,
      autoFeedPlan: false,
      swarmMode: false,
      groundingWeb: false,
      groundingDocs: false,
      groundingFile: false,
      solvingMaxIter: 2, // Default: 2 iterations
      solvingMaxTime: 0, // Default: no time limit
      setMode: (mode) => set({ mode }),
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
      setSkill: (skill) => set({ skill }),
      setStyle: (style) => set({ style }),
      setResearchMode: (researchMode) => set({ researchMode }),
      setUltraplanMode: (ultraplanMode) => set({ ultraplanMode }),
      setUltrathinkMode: (ultrathinkMode) => set({ ultrathinkMode }),
      setAutoFeedPlan: (autoFeedPlan) => set({ autoFeedPlan }),
      setSwarmMode: (swarmMode) => set({ swarmMode }),
      setGroundingWeb: (groundingWeb) => set({ groundingWeb }),
      setGroundingDocs: (groundingDocs) => set({ groundingDocs }),
      setGroundingFile: (groundingFile) => set({ groundingFile }),
      setSolvingMaxIter: (solvingMaxIter) => set({ solvingMaxIter }),
      setSolvingMaxTime: (solvingMaxTime) => set({ solvingMaxTime }),
    }),
    { name: "hive-settings" }
  )
);
