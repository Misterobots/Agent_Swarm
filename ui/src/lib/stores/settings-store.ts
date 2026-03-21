import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  model: string;
  setModel: (model: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      model: "swarm-standard",
      setModel: (model) => set({ model }),
    }),
    { name: "hive-settings" }
  )
);
