import { create } from "zustand";

interface DevState {
  editorContent: string;
  editorLanguage: string;
  setEditorContent: (content: string) => void;
  setEditorLanguage: (language: string) => void;
}

export const useDevStore = create<DevState>((set) => ({
  editorContent: "# Start coding here\n",
  editorLanguage: "python",
  setEditorContent: (content) => set({ editorContent: content }),
  setEditorLanguage: (language) => set({ editorLanguage: language }),
}));
