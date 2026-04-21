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
  groundingWeb: boolean;
  groundingDocs: boolean;
  groundingFile: boolean;
  setMode: (mode: "standard" | "developer") => void;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
  setSkill: (skill: Skill) => void;
  setStyle: (style: Style) => void;
  setResearchMode: (on: boolean) => void;
  setUltraplanMode: (on: boolean) => void;
  setUltrathinkMode: (on: boolean) => void;
  setAutoFeedPlan: (on: boolean) => void;
  setGroundingWeb: (on: boolean) => void;
  setGroundingDocs: (on: boolean) => void;
  setGroundingFile: (on: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      mode: "standard",
      model: "hive-mind",
      theme: "ember",
      skill: "general",
      style: "default",
      researchMode: false,
      ultraplanMode: false,
      ultrathinkMode: false,
      autoFeedPlan: false,
      groundingWeb: false,
      groundingDocs: false,
      groundingFile: false,
      setMode: (mode) => set({ mode }),
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
      setSkill: (skill) => set({ skill }),
      setStyle: (style) => set({ style }),
      setResearchMode: (researchMode) => set({ researchMode }),
      setUltraplanMode: (ultraplanMode) => set({ ultraplanMode }),
      setUltrathinkMode: (ultrathinkMode) => set({ ultrathinkMode }),
      setAutoFeedPlan: (autoFeedPlan) => set({ autoFeedPlan }),
      setGroundingWeb: (groundingWeb) => set({ groundingWeb }),
      setGroundingDocs: (groundingDocs) => set({ groundingDocs }),
      setGroundingFile: (groundingFile) => set({ groundingFile }),
    }),
    { name: "hive-settings" }
  )
);
