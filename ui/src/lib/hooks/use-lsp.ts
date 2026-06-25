"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { desktop } from "@/lib/desktop";

export interface Diagnostic {
  range: {
    start: { line: number; character: number };
    end:   { line: number; character: number };
  };
  severity: 1 | 2 | 3 | 4; // 1=Error 2=Warning 3=Info 4=Hint
  message:  string;
  source?:  string;
  code?:    string | number;
}

const SEVERITY_LABEL = ["", "error", "warning", "info", "hint"] as const;
const SEVERITY_COLOR = ["", "text-red-400", "text-yellow-400", "text-blue-400", "text-[var(--chat-muted)]"] as const;

export { SEVERITY_LABEL, SEVERITY_COLOR };

function extToLang(ext: string): string {
  const map: Record<string, string> = {
    ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts",
    ".py": "py", ".rs": "rs", ".go": "go",
  };
  return map[ext] ?? ext.slice(1);
}

function pathToUri(path: string): string {
  return "file:///" + path.replace(/\\/g, "/").replace(/^\//, "");
}

/**
 * Connects to the LSP for the given file and returns live diagnostics.
 * No-ops gracefully outside the Electron desktop app.
 */
export function useLsp(filePath: string | null, content: string) {
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const versionRef = useRef(1);
  const openedRef  = useRef(false);

  const ext     = filePath ? filePath.slice(filePath.lastIndexOf(".")) : "";
  const lang    = extToLang(ext);
  const fileUri = filePath ? pathToUri(filePath) : null;
  // Root is the parent directory
  const rootUri = fileUri ? fileUri.slice(0, fileUri.lastIndexOf("/")) : null;

  // Start the language server + subscribe to diagnostics
  useEffect(() => {
    const bridge = desktop();
    if (!bridge || !fileUri || !rootUri) return;

    // Subscribe to publishDiagnostics notifications
    const off = bridge.lsp.onNotification(({ method, params }) => {
      if (method !== "textDocument/publishDiagnostics") return;
      const p = params as { uri: string; diagnostics: Diagnostic[] };
      if (p.uri === fileUri) setDiagnostics(p.diagnostics ?? []);
    });

    // Start server (no-op if already running)
    bridge.lsp.start(ext, rootUri).then((started) => {
      if (!started) return;
      // Open document
      bridge.lsp.notify(lang, rootUri, "textDocument/didOpen", {
        textDocument: { uri: fileUri, languageId: lang, version: 1, text: content },
      });
      openedRef.current = true;
    });

    return () => {
      off();
      // Close document on unmount
      if (openedRef.current && rootUri) {
        bridge.lsp.notify(lang, rootUri, "textDocument/didClose", {
          textDocument: { uri: fileUri },
        });
        openedRef.current = false;
      }
      setDiagnostics([]);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileUri, rootUri, lang, ext]);

  // Sync content changes
  const syncContent = useCallback((newContent: string) => {
    const bridge = desktop();
    if (!bridge || !fileUri || !rootUri || !openedRef.current) return;
    bridge.lsp.notify(lang, rootUri, "textDocument/didChange", {
      textDocument: { uri: fileUri, version: ++versionRef.current },
      contentChanges: [{ text: newContent }],
    });
  }, [fileUri, rootUri, lang]);

  return { diagnostics, syncContent };
}
