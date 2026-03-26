import { create } from "zustand";

export type ArtMode = "image" | "3d" | "action-figure";

export interface GenerationEntry {
  id: string;
  mode: ArtMode;
  prompt: string;
  status: "generating" | "complete" | "error";
  result?: string;
  timestamp: number;
}

interface ImageSettings {
  model: string;
  cfg: number;
  steps: number;
  width: number;
  height: number;
  sampler: string;
  scheduler: string;
  seed: number;
}

interface ThreeDSettings {
  workflow: string;
  autoConcept: boolean;
}

interface ActionFigureSettings {
  workflow: string;
  targetHeight: number;
  clearance: number;
}

interface ArtState {
  mode: ArtMode;
  setMode: (mode: ArtMode) => void;

  imageSettings: ImageSettings;
  setImageSettings: (s: Partial<ImageSettings>) => void;

  threeDSettings: ThreeDSettings;
  setThreeDSettings: (s: Partial<ThreeDSettings>) => void;

  actionFigureSettings: ActionFigureSettings;
  setActionFigureSettings: (s: Partial<ActionFigureSettings>) => void;

  history: GenerationEntry[];
  addEntry: (entry: GenerationEntry) => void;
  updateEntry: (id: string, patch: Partial<GenerationEntry>) => void;

  // Redirect from chat
  prefillPrompt: string;
  setPrefillPrompt: (prompt: string) => void;
}

export const useArtStore = create<ArtState>()((set) => ({
  mode: "image",
  setMode: (mode) => set({ mode }),

  imageSettings: {
    model: "auto",
    cfg: 7.0,
    steps: 20,
    width: 1024,
    height: 1024,
    sampler: "euler",
    scheduler: "normal",
    seed: -1,
  },
  setImageSettings: (s) =>
    set((state) => ({ imageSettings: { ...state.imageSettings, ...s } })),

  threeDSettings: {
    workflow: "workflow_triposg.json",
    autoConcept: true,
  },
  setThreeDSettings: (s) =>
    set((state) => ({ threeDSettings: { ...state.threeDSettings, ...s } })),

  actionFigureSettings: {
    workflow: "workflow_triposg.json",
    targetHeight: 150,
    clearance: 0.3,
  },
  setActionFigureSettings: (s) =>
    set((state) => ({
      actionFigureSettings: { ...state.actionFigureSettings, ...s },
    })),

  history: [],
  addEntry: (entry) =>
    set((state) => ({ history: [entry, ...state.history].slice(0, 50) })),
  updateEntry: (id, patch) =>
    set((state) => ({
      history: state.history.map((e) =>
        e.id === id ? { ...e, ...patch } : e
      ),
    })),

  prefillPrompt: "",
  setPrefillPrompt: (prompt) => set({ prefillPrompt: prompt }),
}));
