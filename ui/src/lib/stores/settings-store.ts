import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ChatTheme = "hive" | "neon" | "ember" | "forest";

interface SettingsState {
  mode: "standard" | "developer";
  model: string;
  theme: ChatTheme;
  setMode: (mode: "standard" | "developer") => void;
  setModel: (model: string) => void;
  setTheme: (theme: ChatTheme) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      mode: "standard",
      model: "swarm-standard",
      theme: "hive",
      setMode: (mode) => set({ mode }),
      setModel: (model) => set({ model }),
      setTheme: (theme) => set({ theme }),
    }),
    { name: "hive-settings" }
  )
);
