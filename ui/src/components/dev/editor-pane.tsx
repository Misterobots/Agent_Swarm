"use client";

import { useRef, useCallback, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { FileCode2, Copy, Download, Bot, CheckCircle2, Circle } from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";
import { useModels } from "@/lib/hooks/use-models";
import { useSettingsStore } from "@/lib/stores/settings-store";

type SaveStatus = "saved" | "unsaved" | "idle";

export function EditorPane() {
  const { editorContent, editorLanguage, activeFile, currentProjectId, setEditorContent } = useDevStore();
  const setSelectedText = useDevStore((s) => s.setSelectedText);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const { models, loading: modelsLoading } = useModels();
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);

  // Autosave state
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fadeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveFile = useCallback(async (content: string) => {
    if (!activeFile || !currentProjectId) return;
    try {
      const res = await fetch("/api/backend/v1/dev/files/content", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: currentProjectId,
          path: activeFile,
          content,
          encoding: "utf8",
        }),
      });
      if (res.ok || res.status === 204) {
        const now = new Date();
        setSavedAt(now);
        setSaveStatus("saved");
        // Fade out "Saved" indicator after 3s
        if (fadeTimer.current) clearTimeout(fadeTimer.current);
        fadeTimer.current = setTimeout(() => setSaveStatus("idle"), 3000);
      }
    } catch {
      // Save failed silently — don't disturb the user
    }
  }, [activeFile, currentProjectId]);

  const handleChange = useCallback((value: string | undefined) => {
    const content = value ?? "";
    setEditorContent(content);

    // Only trigger autosave when a file is open and a project is loaded
    if (!activeFile || !currentProjectId) return;

    setSaveStatus("unsaved");
    if (fadeTimer.current) clearTimeout(fadeTimer.current);

    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      saveFile(content);
    }, 1500);
  }, [setEditorContent, activeFile, currentProjectId, saveFile]);

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

  const handleCopy = useCallback(() => {
    if (editorRef.current) {
      const value = editorRef.current.getValue();
      navigator.clipboard.writeText(value);
    }
  }, []);

  const handleDownload = useCallback(() => {
    if (editorRef.current) {
      const value = editorRef.current.getValue();
      const blob = new Blob([value], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const fileName = activeFile ? activeFile.split("/").pop() ?? `code.${editorLanguage}` : `code.${editorLanguage}`;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [editorLanguage, activeFile]);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2 text-xs text-[var(--chat-muted)]">
          <FileCode2 size={13} />
          <span className="truncate max-w-[200px]" title={activeFile || "Editor"}>
            {activeFile ? activeFile.split("/").pop() : "Editor"}
          </span>
          <select
            value={editorLanguage}
            onChange={(e) => useDevStore.getState().setEditorLanguage(e.target.value)}
            className="ml-2 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-2 py-0.5 text-xs text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]/40"
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
            <option value="plaintext">Plain Text</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          {/* Save status indicator */}
          {saveStatus === "unsaved" && (
            <span className="flex items-center gap-1 text-[10px] text-[var(--chat-muted)]">
              <Circle size={8} className="text-amber-400" />
              Unsaved
            </span>
          )}
          {saveStatus === "saved" && savedAt && (
            <span className="flex items-center gap-1 text-[10px] text-[var(--chat-muted)]">
              <CheckCircle2 size={10} className="text-emerald-400" />
              Saved {savedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          )}

          {/* Model selector */}
          <div className="flex items-center gap-1">
            <Bot size={13} className="text-[var(--chat-muted)]" />
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={modelsLoading}
              className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-2 py-0.5 text-xs text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]/40 max-w-[160px]"
            >
              {models.length > 0 ? (
                <>
                  {models.filter(m => !m.id.startsWith("github/")).length > 0 && (
                    <optgroup label="Local">
                      {models.filter(m => !m.id.startsWith("github/")).map((m) => (
                        <option key={m.id} value={m.id}>{m.id}</option>
                      ))}
                    </optgroup>
                  )}
                  {models.filter(m => m.id.startsWith("github/")).length > 0 && (
                    <optgroup label="GitHub">
                      {models.filter(m => m.id.startsWith("github/")).map((m) => (
                        <option key={m.id} value={m.id}>{m.id.replace("github/", "")}</option>
                      ))}
                    </optgroup>
                  )}
                </>
              ) : (
                <option value="Home-AI-Swarm">Home-AI-Swarm</option>
              )}
            </select>
          </div>
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
        <Editor
          height="100%"
          language={editorLanguage}
          value={editorContent}
          onChange={handleChange}
          onMount={handleMount}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            tabSize: 2,
            automaticLayout: true,
            padding: { top: 8 },
            renderLineHighlight: "gutter",
            cursorBlinking: "smooth",
            smoothScrolling: true,
          }}
        />
      </div>
    </div>
  );
}
