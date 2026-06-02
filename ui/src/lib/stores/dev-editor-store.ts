/**
 * Dev Editor slice — owns: editorContent, activeFile, editorLanguage, selectedText.
 * Primary writer: task W1.
 *
 * New code should import from this store directly rather than via the dev-store facade.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface DevEditorState {
  editorContent: string;
  editorLanguage: string;
  activeFile: string;
  selectedText: string;

  setEditorContent: (content: string) => void;
  setEditorLanguage: (language: string) => void;
  setActiveFile: (file: string) => void;
  setSelectedText: (text: string) => void;
}

export const useDevEditorStore = create<DevEditorState>()(
  persist(
    (set) => ({
      editorContent: "# Start coding here\n",
      editorLanguage: "python",
      activeFile: "",
      selectedText: "",

      setEditorContent: (content) => set({ editorContent: content }),
      setEditorLanguage: (language) => set({ editorLanguage: language }),
      setActiveFile: (file) => set({ activeFile: file }),
      setSelectedText: (text) => set({ selectedText: text }),
    }),
    {
      name: "memex-dev-editor-store",
    }
  )
);
