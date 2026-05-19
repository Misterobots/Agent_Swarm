"use client";

import { useRef, useState } from "react";
import { useDevStore } from "@/lib/stores/dev-store";
import { ExternalLink, RefreshCw, X, Monitor } from "lucide-react";

export function ChatPreviewPane() {
  const previewUrl = useDevStore((s) => s.previewUrl);
  const previewUnavailable = useDevStore((s) => s.previewUnavailable);
  const setShowChatPreview = useDevStore((s) => s.setShowChatPreview);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loading, setLoading] = useState(true);

  const handleRefresh = () => {
    setLoading(true);
    if (iframeRef.current) {
      // eslint-disable-next-line no-self-assign
      iframeRef.current.src = iframeRef.current.src;
    }
  };

  return (
    <div className="hidden md:flex flex-col h-full w-[42%] min-w-[380px] max-w-[640px] border-l border-[var(--chat-border)] bg-[var(--chat-surface)] flex-shrink-0">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--chat-border)] flex-shrink-0 bg-[var(--chat-panel)]">
        <Monitor size={14} className="text-[var(--chat-muted)] flex-shrink-0" />
        <span className="text-xs font-medium text-[var(--chat-muted)] flex-1 truncate">
          {previewUnavailable ? "Preview" : previewUrl || "Preview"}
        </span>
        {!previewUnavailable && previewUrl && (
          <>
            <button
              type="button"
              onClick={handleRefresh}
              className="p-1 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
              title="Refresh"
            >
              <RefreshCw size={13} />
            </button>
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
              title="Open in new tab"
            >
              <ExternalLink size={13} />
            </a>
          </>
        )}
        <button
          type="button"
          onClick={() => setShowChatPreview(false)}
          className="p-1 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          title="Close preview"
        >
          <X size={13} />
        </button>
      </div>

      {/* Content area */}
      <div className="flex-1 relative overflow-hidden">
        {previewUnavailable ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[var(--chat-bg)] px-8 text-center">
            <Monitor size={40} className="text-[var(--chat-muted)] opacity-30" />
            <p className="text-sm font-medium text-[var(--chat-text)]">Preview not available</p>
            <p className="text-xs text-[var(--chat-muted)] leading-relaxed">
              This build doesn&apos;t produce a web interface. Launch it locally or check the output above for instructions.
            </p>
          </div>
        ) : previewUrl ? (
          <>
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-[var(--chat-bg)] z-10">
                <div className="w-6 h-6 rounded-full border-2 border-[var(--chat-accent)] border-t-transparent animate-spin" />
              </div>
            )}
            <iframe
              ref={iframeRef}
              src={previewUrl}
              className="w-full h-full border-0 block"
              sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups"
              onLoad={() => setLoading(false)}
              title="App preview"
            />
          </>
        ) : null}
      </div>
    </div>
  );
}
