"use client";

import { useEffect, useRef, useCallback } from "react";
import { BookOpen, ExternalLink } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { Loader2, AlertTriangle } from "lucide-react";
import { useState } from "react";

const DOCS_URL = "/docs-site/";

export function DocsView() {
  const theme = useSettingsStore((s) => s.theme);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  /** Send the current theme to the docs iframe */
  const sendTheme = useCallback(() => {
    const iframe = iframeRef.current;
    if (iframe?.contentWindow) {
      iframe.contentWindow.postMessage({ type: "theme-sync", theme }, "*");
    }
  }, [theme]);

  // Re-send theme whenever it changes
  useEffect(() => {
    sendTheme();
  }, [sendTheme]);

  // Listen for theme-request from the iframe (sent on its DOMContentLoaded)
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.data?.type === "theme-request") {
        sendTheme();
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [sendTheme]);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] text-[var(--chat-text)]">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-[var(--chat-accent)]" />
          <span className="text-sm font-medium">Documentation</span>
        </div>
        <a
          href={DOCS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors"
        >
          Open full site
          <ExternalLink size={12} />
        </a>
      </div>

      {/* Iframe */}
      <div className="relative flex-1">
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-[var(--chat-bg)]">
            <div className="flex flex-col items-center gap-3">
              <Loader2 size={24} className="text-[var(--chat-accent)] animate-spin" />
              <span className="text-sm text-[var(--chat-muted)]">Loading Documentation...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-[var(--chat-bg)]">
            <div className="flex flex-col items-center gap-3">
              <AlertTriangle size={24} className="text-red-400" />
              <span className="text-sm text-red-300">Failed to load Documentation</span>
              <span className="text-xs text-[var(--chat-muted)]">The service may be unavailable or blocking iframe embedding.</span>
            </div>
          </div>
        )}

        <iframe
          ref={iframeRef}
          src={DOCS_URL}
          title="Documentation"
          className="w-full h-full border-0"
          style={{ height: "calc(100vh - 6.5rem)" }}
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-downloads"
          onLoad={() => {
            setLoading(false);
            sendTheme();
          }}
          onError={() => {
            setLoading(false);
            setError(true);
          }}
        />
      </div>
    </div>
  );
}
