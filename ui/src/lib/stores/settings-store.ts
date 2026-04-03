import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  model: string;
  theme: ChatTheme;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
}

export type ChatTheme = "ember" | "slate" | "signal";

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      model: "swarm-standard",
      theme: "ember",
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
    }),
    { name: "hive-settings" }
  )
);
