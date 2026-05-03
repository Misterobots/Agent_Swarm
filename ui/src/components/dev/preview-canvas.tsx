"use client";

import { useState, useEffect } from "react";
import { useDevStore } from "@/lib/stores/dev-store";
import { Play, RefreshCw, ExternalLink } from "lucide-react";

export function PreviewCanvas() {
  const { previewUrl } = useDevStore();
  const [iframeKey, setIframeKey] = useState(0);
  const [loading, setLoading] = useState(true);

  const handleRefresh = () => {
    setLoading(true);
    setIframeKey((prev) => prev + 1);
  };

  const handleOpenExternal = () => {
    window.open(previewUrl, "_blank");
  };

  useEffect(() => {
    setLoading(true);
    setIframeKey((prev) => prev + 1);
  }, [previewUrl]);

  return (
    <div className="h-full flex flex-col bg-[var(--chat-bg)]">
      {/* Preview Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--chat-surface)] border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2">
          <Play size={16} className="text-[var(--chat-accent)]" />
          <span className="text-sm font-medium text-[var(--chat-text)]">Live Preview</span>
          <span className="text-xs text-[var(--chat-muted)]">({previewUrl})</span>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-2 py-1 text-xs rounded bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            title="Refresh preview"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
          <button
            onClick={handleOpenExternal}
            className="flex items-center gap-1.5 px-2 py-1 text-xs rounded bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            title="Open in new tab"
          >
            <ExternalLink size={14} />
            Open
          </button>
        </div>
      </div>

      {/* Preview Frame */}
      <div className="flex-1 relative bg-white">
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
          title="Application Preview"
        />
      </div>
    </div>
  );
}
