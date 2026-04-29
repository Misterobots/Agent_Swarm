"use client";

import { useRef, useCallback, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { FileCode2, Copy, Download, X, Plus, Save } from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";

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

export function TabbedEditor() {
  const [tabs, setTabs] = useState<EditorTab[]>([DEFAULT_TAB]);
  const [activeTabId, setActiveTabId] = useState(DEFAULT_TAB.id);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const { setSelectedText } = useDevStore();

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0];

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
    editor.focus();
    editor.onDidChangeCursorSelection(() => {
      const selection = editor.getSelection();
      if (selection && !selection.isEmpty()) {
        const text = editor.getModel()?.getValueInRange(selection) ?? "";
        setSelectedText(text);
      } else {
        setSelectedText("");
      }
    });
  };

  const handleContentChange = (value: string | undefined) => {
    if (value === undefined) return;
    setTabs((prev) =>
      prev.map((tab) =>
        tab.id === activeTabId
          ? { ...tab, content: value, modified: true }
          : tab
      )
    );
  };

  const createNewTab = () => {
    const newId = `untitled-${Date.now()}`;
    const newTab: EditorTab = {
      id: newId,
      path: "",
      filename: `Untitled ${tabs.length + 1}`,
      language: "python",
      content: "# Start coding here\n",
      modified: false,
    };
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newId);
  };

  const closeTab = (tabId: string) => {
    const tab = tabs.find((t) => t.id === tabId);
    if (tab?.modified) {
      if (!confirm(`${tab.filename} has unsaved changes. Close anyway?`)) {
        return;
      }
    }

    setTabs((prev) => {
      const filtered = prev.filter((t) => t.id !== tabId);
      if (filtered.length === 0) {
        // Keep at least one tab
        return [DEFAULT_TAB];
      }
      if (tabId === activeTabId) {
        const currentIndex = prev.findIndex((t) => t.id === tabId);
        const nextTab = filtered[currentIndex] || filtered[currentIndex - 1] || filtered[0];
        setActiveTabId(nextTab.id);
      }
      return filtered;
    });
  };

  const saveFile = async () => {
    if (!activeTab) return;
    
    try {
      const response = await fetch("/api/devops/files/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: activeTab.path || `/workspace/${activeTab.filename}`,
          content: activeTab.content,
        }),
      });

      if (response.ok) {
        setTabs((prev) =>
          prev.map((tab) =>
            tab.id === activeTabId ? { ...tab, modified: false } : tab
          )
        );
      }
    } catch (error) {
      console.error("Failed to save file:", error);
    }
  };

  const handleCopy = useCallback(() => {
    if (editorRef.current) {
      const value = editorRef.current.getValue();
      navigator.clipboard.writeText(value);
    }
  }, []);

  const handleDownload = useCallback(() => {
    if (editorRef.current && activeTab) {
      const value = editorRef.current.getValue();
      const blob = new Blob([value], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = activeTab.filename;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [activeTab]);

  const detectLanguage = (filename: string): string => {
    const ext = filename.split(".").pop()?.toLowerCase();
    const langMap: Record<string, string> = {
      py: "python",
      js: "javascript",
      ts: "typescript",
      tsx: "typescript",
      jsx: "javascript",
      json: "json",
      yaml: "yaml",
      yml: "yaml",
      md: "markdown",
      sh: "shell",
      bash: "shell",
      dockerfile: "dockerfile",
      css: "css",
      html: "html",
      sql: "sql",
    };
    return langMap[ext || ""] || "plaintext";
  };

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
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
              
              {/* Close button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeTab(tab.id);
                }}
                className="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>

        {/* Add new tab button */}
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
          <select
            value={activeTab?.language || "python"}
            onChange={(e) =>
              setTabs((prev) =>
                prev.map((tab) =>
                  tab.id === activeTabId
                    ? { ...tab, language: e.target.value }
                    : tab
                )
              )
            }
            className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-2 py-0.5 text-xs text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]/40"
          >
            <option value="python">Python</option>
            <option value="typescript">TypeScript</option>
            <option value="javascript">JavaScript</option>
            <option value="json">JSON</option>
            <option value="yaml">YAML</option>
            <option value="markdown">Markdown</option>
            <option value="shell">Shell</option>
            <option value="dockerfile">Dockerfile</option>
            <option value="css">CSS</option>
            <option value="html">HTML</option>
            <option value="sql">SQL</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={saveFile}
            disabled={!activeTab?.modified}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Save file (Ctrl+S)"
          >
            <Save size={13} />
            Save
          </button>
          <div className="w-px h-4 bg-[var(--chat-border)]" />
          <button
            onClick={handleCopy}
            className="p-1.5 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)] transition-colors"
            title="Copy to clipboard"
          >
            <Copy size={13} />
          </button>
          <button
            onClick={handleDownload}
            className="p-1.5 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)] transition-colors"
            title="Download file"
          >
            <Download size={13} />
          </button>
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1">
        {activeTab && (
          <Editor
            key={activeTab.id}
            height="100%"
            language={activeTab.language}
            value={activeTab.content}
            onChange={handleContentChange}
            onMount={handleMount}
            theme="vs-dark"
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
              suggest: {
                showKeywords: true,
                showSnippets: true,
              },
            }}
          />
        )}
      </div>
    </div>
  );
}
