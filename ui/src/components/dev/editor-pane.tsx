"use client";

import { useRef, useCallback } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import { FileCode2, Copy, Download } from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";

export function EditorPane() {
  const { editorContent, editorLanguage, setEditorContent } = useDevStore();
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
    editor.focus();
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
    <div className="flex flex-col h-full bg-[#0e1117]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <FileCode2 size={13} />
          <span>Editor</span>
          <select
            value={editorLanguage}
            onChange={(e) => useDevStore.getState().setEditorLanguage(e.target.value)}
            className="ml-2 bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 text-xs text-zinc-400 focus:outline-none focus:border-cyan-800"
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
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            title="Copy to clipboard"
          >
            <Copy size={13} />
          </button>
          <button
            onClick={handleDownload}
            className="p-1.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
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
