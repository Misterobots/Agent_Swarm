"use client";

import { useRef, useCallback, useState, useEffect } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { FileCode2, Copy, Download, X, Plus, Save, Loader2, PanelLeft } from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";
import { useDevEditorStore } from "@/lib/stores/dev-editor-store";
import { useDevProjectStore } from "@/lib/stores/dev-project-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useDevPanelStore } from "@/lib/stores/dev-panel-store";
import { FileTree } from "./file-tree";
import { getMonacoThemeName, registerMonacoThemes } from "./dev-theme-map";

interface EditorTab {
  id: string;
  path: string;
  filename: string;
  language: string;
  content: string;
  modified: boolean;
}

const DEFAULT_TAB: EditorTab = {
  id: "untitled-1",
  path: "",
  filename: "Untitled",
  language: "python",
  content: "# Start coding here\n",
  modified: false,
};

const LANG_MAP: Record<string, string> = {
  py: "python", ts: "typescript", tsx: "typescript",
  js: "javascript", jsx: "javascript", json: "json",
  md: "markdown", yaml: "yaml", yml: "yaml",
  sh: "shell", css: "css", html: "html", sql: "sql",
  dockerfile: "dockerfile",
};

function detectLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return LANG_MAP[ext] || "plaintext";
}

export function TabbedEditor() {
  const [tabs, setTabs] = useState<EditorTab[]>([DEFAULT_TAB]);
  const [activeTabId, setActiveTabId] = useState(DEFAULT_TAB.id);
  const [saving, setSaving] = useState(false);

  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  // Always-current ref to saveFile so the Monaco Ctrl+S command never closes over a stale version
  const saveFileRef = useRef<() => Promise<void>>(() => Promise.resolve());
  // Mirror of tabs for use inside effects without adding to dependency arrays
  const tabsRef = useRef(tabs);
  useEffect(() => { tabsRef.current = tabs; });

  const didRestoreRef = useRef(false);
  const prevActiveFileRef = useRef("");

  const { setSelectedText } = useDevStore();
  const {
    activeFile, editorContent, editorLanguage,
    setHasUnsavedChanges,
    openTabMeta, activeTabPath,
    setOpenTabMeta, setActiveTabPath,
  } = useDevEditorStore();
  const { currentProjectId } = useDevProjectStore();
  const { theme: themeId, themeMode } = useSettingsStore();
  const { showFileTree, setShowFileTree } = useDevPanelStore();
  const isLight = themeMode === "light";
  const monacoTheme = getMonacoThemeName(themeId, isLight);

  // ── Monaco theme setup ────────────────────────────────────────────────────
  useEffect(() => { registerMonacoThemes(); }, []);
  useEffect(() => {
    import("@monaco-editor/react").then(({ loader }) =>
      loader.init().then((monaco) => monaco.editor.setTheme(monacoTheme))
    );
  }, [monacoTheme]);

  // ── Sync unsaved-changes flag to store (for ProjectSwitcher guard) ─────────
  useEffect(() => {
    setHasUnsavedChanges(tabs.some((t) => t.modified));
  }, [tabs, setHasUnsavedChanges]);

  // ── Persist open tab metadata for session restoration ─────────────────────
  useEffect(() => {
    const meta = tabs
      .filter((t) => t.path)
      .map(({ path, filename, language }) => ({ path, filename, language }));
    setOpenTabMeta(meta);
  }, [tabs, setOpenTabMeta]);

  useEffect(() => {
    const active = tabs.find((t) => t.id === activeTabId);
    setActiveTabPath(active?.path ?? null);
  }, [activeTabId, tabs, setActiveTabPath]);

  // ── Session restoration — re-fetch previously open files on mount ──────────
  useEffect(() => {
    if (didRestoreRef.current || !currentProjectId || openTabMeta.length === 0) return;
    didRestoreRef.current = true;

    Promise.all(
      openTabMeta.map(async (meta) => {
        try {
          const res = await fetch(
            `/api/backend/v1/dev/files/content?project_id=${currentProjectId}&path=${encodeURIComponent(meta.path)}`
          );
          if (!res.ok) return null;
          const { content, encoding } = await res.json();
          if (encoding === "base64") return null;
          return { ...meta, content } as EditorTab & { content: string };
        } catch {
          return null;
        }
      })
    ).then((results) => {
      const valid = results.filter(Boolean) as (typeof results[number] & object)[];
      if (valid.length === 0) return;
      const restoredTabs: EditorTab[] = (valid as NonNullable<typeof valid[number]>[]).map((m) => ({
        id: (m as { path: string }).path,
        path: (m as { path: string }).path,
        filename: (m as { filename: string }).filename,
        language: (m as { language: string }).language,
        content: (m as { content: string }).content,
        modified: false,
      }));
      setTabs(restoredTabs);
      const targetId = activeTabPath
        ? (restoredTabs.find((t) => t.path === activeTabPath)?.id ?? restoredTabs[0].id)
        : restoredTabs[0].id;
      setActiveTabId(targetId);
      prevActiveFileRef.current = targetId;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProjectId]);

  // ── React to file-tree clicks: open or switch to the file ─────────────────
  useEffect(() => {
    if (!activeFile || activeFile === prevActiveFileRef.current) return;
    prevActiveFileRef.current = activeFile;

    const existing = tabsRef.current.find((t) => t.path === activeFile);
    if (existing) {
      setActiveTabId(existing.id);
      return;
    }

    // Get the latest content from the store imperatively (avoids stale closure)
    const store = useDevEditorStore.getState();
    const content = store.editorContent ?? "";
    const lang = store.editorLanguage || detectLanguage(activeFile);
    const filename = activeFile.split("/").pop() || activeFile;

    const newTab: EditorTab = {
      id: activeFile,
      path: activeFile,
      filename,
      language: lang,
      content,
      modified: false,
    };

    setTabs((prev) => {
      // Replace the sole default empty tab if it's unmodified
      if (prev.length === 1 && !prev[0].path && !prev[0].modified) return [newTab];
      return [...prev, newTab];
    });
    setActiveTabId(activeFile);
  }, [activeFile]);

  // ── Derived active tab ────────────────────────────────────────────────────
  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0];

  // ── Save to disk ──────────────────────────────────────────────────────────
  const saveFile = useCallback(async () => {
    if (!activeTab?.path || !currentProjectId || saving) return;
    setSaving(true);
    try {
      const res = await fetch(
        `/api/backend/v1/dev/files/content?project_id=${currentProjectId}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: activeTab.path, content: activeTab.content, encoding: "utf8" }),
        }
      );
      if (res.ok || res.status === 204) {
        setTabs((prev) =>
          prev.map((tab) => (tab.id === activeTab.id ? { ...tab, modified: false } : tab))
        );
      }
    } catch (err) {
      console.error("Save failed:", err);
    } finally {
      setSaving(false);
    }
  }, [activeTab, currentProjectId, saving]);

  // Keep the ref always current so the Monaco Ctrl+S command is never stale
  useEffect(() => { saveFileRef.current = saveFile; });

  // ── Monaco mount ──────────────────────────────────────────────────────────
  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    editor.focus();

    // Ctrl+S / Cmd+S → save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      saveFileRef.current();
    });

    editor.onDidChangeCursorSelection(() => {
      const selection = editor.getSelection();
      if (selection && !selection.isEmpty()) {
        setSelectedText(editor.getModel()?.getValueInRange(selection) ?? "");
      } else {
        setSelectedText("");
      }
    });
  };

  // ── Tab management ────────────────────────────────────────────────────────
  const handleContentChange = (value: string | undefined) => {
    if (value === undefined) return;
    setTabs((prev) =>
      prev.map((tab) => (tab.id === activeTabId ? { ...tab, content: value, modified: true } : tab))
    );
  };

  const createNewTab = () => {
    const newId = `untitled-${Date.now()}`;
    setTabs((prev) => [
      ...prev,
      { id: newId, path: "", filename: `Untitled ${prev.length + 1}`, language: "python", content: "# Start coding here\n", modified: false },
    ]);
    setActiveTabId(newId);
  };

  const closeTab = (tabId: string) => {
    const tab = tabs.find((t) => t.id === tabId);
    if (tab?.modified && !confirm(`${tab.filename} has unsaved changes. Close anyway?`)) return;
    setTabs((prev) => {
      const filtered = prev.filter((t) => t.id !== tabId);
      if (filtered.length === 0) return [DEFAULT_TAB];
      if (tabId === activeTabId) {
        const idx = prev.findIndex((t) => t.id === tabId);
        const next = filtered[idx] ?? filtered[idx - 1] ?? filtered[0];
        setActiveTabId(next.id);
      }
      return filtered;
    });
  };

  // ── Toolbar actions ───────────────────────────────────────────────────────
  const handleCopy = useCallback(() => {
    if (editorRef.current) navigator.clipboard.writeText(editorRef.current.getValue());
  }, []);

  const handleDownload = useCallback(() => {
    if (!editorRef.current || !activeTab) return;
    const blob = new Blob([editorRef.current.getValue()], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: activeTab.filename });
    a.click();
    URL.revokeObjectURL(url);
  }, [activeTab]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full bg-[var(--chat-bg)]">
      {/* File tree sidebar */}
      {showFileTree && (
        <div className="w-48 flex-shrink-0 overflow-hidden">
          <FileTree />
        </div>
      )}

      {/* Editor column */}
      <div className="flex flex-col flex-1 min-w-0 h-full bg-[var(--chat-bg)]">
      {/* Tab Bar */}
      <div className="flex items-center border-b border-[var(--chat-border)] bg-[var(--chat-bg)]">
        <div className="flex flex-1 overflow-x-auto">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`group flex items-center gap-2 px-3 py-2 text-xs cursor-pointer transition-colors border-r border-[var(--chat-border)] ${
                tab.id === activeTabId
                  ? "text-[var(--chat-accent)] bg-[var(--chat-input-bg)] border-b-2 border-[var(--chat-accent)]"
                  : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-hover)]"
              }`}
              onClick={() => setActiveTabId(tab.id)}
            >
              <FileCode2 size={14} />
              <span>{tab.filename}</span>
              {tab.modified && <span className="text-[var(--chat-accent)]">●</span>}
              <button
                onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}
                className="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={createNewTab}
          className="px-3 py-2 text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors"
          title="New file"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2 text-xs text-[var(--chat-muted)]">
          <button
            onClick={() => setShowFileTree(!showFileTree)}
            className={`p-1.5 rounded transition-colors ${showFileTree ? "text-[var(--chat-accent)] bg-[var(--chat-accent-soft)]" : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)]"}`}
            title={showFileTree ? "Hide file tree" : "Show file tree"}
          >
            <PanelLeft size={13} />
          </button>
          <div className="w-px h-4 bg-[var(--chat-border)]" />
          <select
            value={activeTab?.language || "python"}
            onChange={(e) =>
              setTabs((prev) =>
                prev.map((tab) => (tab.id === activeTabId ? { ...tab, language: e.target.value } : tab))
              )
            }
            className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-2 py-0.5 text-xs text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]/40"
          >
            {["python","typescript","javascript","json","yaml","markdown","shell","dockerfile","css","html","sql"].map((l) => (
              <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={saveFile}
            disabled={!activeTab?.modified || !activeTab?.path || !currentProjectId || saving}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Save file (Ctrl+S)"
          >
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            Save
          </button>
          <div className="w-px h-4 bg-[var(--chat-border)]" />
          <button onClick={handleCopy} className="p-1.5 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)] transition-colors" title="Copy to clipboard">
            <Copy size={13} />
          </button>
          <button onClick={handleDownload} className="p-1.5 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)] transition-colors" title="Download file">
            <Download size={13} />
          </button>
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0">
        {activeTab && (
          <Editor
            key={activeTab.id}
            height="100%"
            language={activeTab.language}
            value={activeTab.content}
            onChange={handleContentChange}
            onMount={handleMount}
            theme={monacoTheme}
            options={{
              minimap: { enabled: true },
              fontSize: 13,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
              tabSize: 2,
              automaticLayout: true,
              padding: { top: 8 },
              renderLineHighlight: "all",
              cursorBlinking: "smooth",
              smoothScrolling: true,
              formatOnPaste: true,
              formatOnType: true,
              suggest: { showKeywords: true, showSnippets: true },
            }}
          />
        )}
      </div>
      </div>{/* end editor column */}
    </div>
  );
}
