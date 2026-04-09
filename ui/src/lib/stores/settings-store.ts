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
  setMode: (mode: "standard" | "developer") => void;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
  setSkill: (skill: Skill) => void;
  setStyle: (style: Style) => void;
  setResearchMode: (on: boolean) => void;
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
      setMode: (mode) => set({ mode }),
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
      setSkill: (skill) => set({ skill }),
      setStyle: (style) => set({ style }),
      setResearchMode: (researchMode) => set({ researchMode }),
    }),
    { name: "hive-settings" }
  )
);
