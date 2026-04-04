import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Skill, Style } from "@/types/chat";

interface SettingsState {
  model: string;
  theme: ChatTheme;
  skill: Skill;
  style: Style;
  researchMode: boolean;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
  setSkill: (skill: Skill) => void;
  setStyle: (style: Style) => void;
  setResearchMode: (on: boolean) => void;
}

export type ChatTheme = "ember" | "slate" | "signal" | "office" | "hacker" | "star-trek" | "cyberpunk" | "minimal";

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      model: "swarm-standard",
      theme: "ember",
      skill: "general",
      style: "default",
      researchMode: false,
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
      setSkill: (skill) => set({ skill }),
      setStyle: (style) => set({ style }),
      setResearchMode: (researchMode) => set({ researchMode }),
    }),
    { name: "hive-settings" }
  )
);
