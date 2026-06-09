/**
 * Dev Editor slice — owns: editorContent, activeFile, editorLanguage, selectedText.
 * Primary writer: task W1.
 *
 * New code should import from this store directly rather than via the dev-store facade.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface TabMeta {
  path: string;
  filename: string;
  language: string;
}

export interface DevEditorState {
  editorContent: string;
  editorLanguage: string;
  activeFile: string;
  selectedText: string;
  hasUnsavedChanges: boolean;
  /** Persisted list of open file paths for session restoration on reload */
  openTabMeta: TabMeta[];
  /** Path of the active tab at last session — restored on mount */
  activeTabPath: string | null;

  setEditorContent: (content: string) => void;
  setEditorLanguage: (language: string) => void;
  setActiveFile: (file: string) => void;
  setSelectedText: (text: string) => void;
  setHasUnsavedChanges: (v: boolean) => void;
  setOpenTabMeta: (tabs: TabMeta[]) => void;
  setActiveTabPath: (path: string | null) => void;
}

export const useDevEditorStore = create<DevEditorState>()(
  persist(
    (set) => ({
      editorContent: "# Start coding here\n",
      editorLanguage: "python",
      activeFile: "",
      selectedText: "",
      hasUnsavedChanges: false,
      openTabMeta: [],
      activeTabPath: null,

      setEditorContent: (content) => set({ editorContent: content }),
      setEditorLanguage: (language) => set({ editorLanguage: language }),
      setActiveFile: (file) => set({ activeFile: file }),
      setSelectedText: (text) => set({ selectedText: text }),
      setHasUnsavedChanges: (v) => set({ hasUnsavedChanges: v }),
      setOpenTabMeta: (tabs) => set({ openTabMeta: tabs }),
      setActiveTabPath: (path) => set({ activeTabPath: path }),
    }),
    {
      name: "memex-dev-editor-store",
    }
  )
);
