"use client";

import { useState, useEffect, useRef } from "react";
import { useDevStore } from "@/lib/stores/dev-store";
import { Play, RefreshCw, ExternalLink, Monitor } from "lucide-react";

export function PreviewCanvas() {
  const { previewUrl, setPreviewUrl } = useDevStore();
  const [iframeKey, setIframeKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [urlInput, setUrlInput] = useState(previewUrl);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleRefresh = () => {
    if (!previewUrl) return;
    setLoading(true);
    setIframeKey((prev) => prev + 1);
  };

  const handleOpenExternal = () => {
    if (previewUrl) window.open(previewUrl, "_blank");
  };

  const handleNavigate = (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = urlInput.trim();
    if (!trimmed) return;
    // Auto-prefix http:// if missing scheme
    const url = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
    setUrlInput(url);
    setPreviewUrl(url);
  };

  useEffect(() => {
    if (previewUrl) {
      setLoading(true);
      setIframeKey((prev) => prev + 1);
    }
  }, [previewUrl]);

  return (
    <div className="h-full flex flex-col bg-[var(--chat-bg)]">
      {/* URL Bar */}
      <form
        onSubmit={handleNavigate}
        className="flex items-center gap-2 px-4 py-2 bg-[var(--chat-surface)] border-b border-[var(--chat-border)]"
      >
        <Play size={14} className="text-[var(--chat-accent)] flex-shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          onBlur={() => handleNavigate()}
          placeholder="Enter URL, e.g. http://192.168.2.103:8080"
          className="flex-1 min-w-0 bg-[var(--chat-input-bg)] border border-[var(--chat-border)] rounded px-2 py-1 text-xs text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]"
        />
        <button
          type="submit"
          className="px-2 py-1 text-xs rounded bg-[var(--chat-accent)] text-white hover:opacity-90 transition-opacity"
        >
          Go
        </button>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={!previewUrl}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40"
          title="Refresh"
        >
          <RefreshCw size={12} />
        </button>
        <button
          type="button"
          onClick={handleOpenExternal}
          disabled={!previewUrl}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40"
          title="Open in new tab"
        >
          <ExternalLink size={12} />
        </button>
      </form>

      {/* Preview Frame or empty state */}
      <div className="flex-1 relative bg-white">
        {!previewUrl ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 bg-[var(--chat-bg)] text-[var(--chat-muted)]">
            <Monitor size={40} className="opacity-30" />
            <div className="text-center">
              <p className="text-sm font-medium text-[var(--chat-text)]">No preview URL set</p>
              <p className="text-xs mt-1">Enter a URL above to preview a running app</p>
              <p className="text-xs mt-0.5 opacity-60">e.g. http://192.168.2.103:8080 or http://localhost:3000</p>
            </div>
          </div>
        ) : (
          <>
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-[var(--chat-bg)] z-10">
                <div className="flex flex-col items-center gap-3">
                  <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--chat-accent)] border-t-transparent" />
                  <span className="text-sm text-[var(--chat-muted)]">Loading preview...</span>
                </div>
              </div>
            )}
            <iframe
              key={iframeKey}
              src={previewUrl}
              className="w-full h-full border-0"
              sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups"
              onLoad={() => setLoading(false)}
              onError={() => setLoading(false)}
              title="Application Preview"
            />
          </>
        )}
      </div>
    </div>
  );
}
