import { create } from "zustand";

interface DevState {
  editorContent: string;
  editorLanguage: string;
  activeFile: string;
  selectedText: string;
  setEditorContent: (content: string) => void;
  setEditorLanguage: (language: string) => void;
  setActiveFile: (file: string) => void;
  setSelectedText: (text: string) => void;
}

export const useDevStore = create<DevState>((set) => ({
  editorContent: "# Start coding here\n",
  editorLanguage: "python",
  activeFile: "",
  selectedText: "",
  setEditorContent: (content) => set({ editorContent: content }),
  setEditorLanguage: (language) => set({ editorLanguage: language }),
  setActiveFile: (file) => set({ activeFile: file }),
  setSelectedText: (text) => set({ selectedText: text }),
}));
