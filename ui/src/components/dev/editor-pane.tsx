"use client";

import { useRef, useCallback } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { FileCode2, Copy, Download, Bot } from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";
import { useModels } from "@/lib/hooks/use-models";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function EditorPane() {
  const { editorContent, editorLanguage, setEditorContent } = useDevStore();
  const setSelectedText = useDevStore((s) => s.setSelectedText);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const { models, loading: modelsLoading } = useModels();
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);

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
      a.download = `code.${editorLanguage}`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [editorLanguage]);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2 text-xs text-[var(--chat-muted)]">
          <FileCode2 size={13} />
          <span>Editor</span>
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
          </select>
        </div>
        <div className="flex items-center gap-2">
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
      </div>

      {/* Monaco Editor */}
      <div className="flex-1">
        <Editor
          height="100%"
          language={editorLanguage}
          value={editorContent}
          onChange={(value) => setEditorContent(value || "")}
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
