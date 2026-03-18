import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  mode: "standard" | "developer";
  model: string;
  setMode: (mode: "standard" | "developer") => void;
  setModel: (model: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      mode: "standard",
      model: "swarm-standard",
      setMode: (mode) => set({ mode }),
      setModel: (model) => set({ model }),
    }),
    { name: "hive-settings" }
  )
);
