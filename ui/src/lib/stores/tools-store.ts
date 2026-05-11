import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ToolsState {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const useToolsStore = create<ToolsState>()(
  persist(
    (set) => ({
      activeTab: "openhands",
      setActiveTab: (tab) => set({ activeTab: tab }),
    }),
    { name: "memex-tools" }
  )
);
