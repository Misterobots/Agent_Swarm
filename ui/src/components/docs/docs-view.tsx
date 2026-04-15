"use client";

import { BookOpen, ExternalLink } from "lucide-react";
import { ToolIframe } from "@/components/tools/tool-iframe";

const DOCS_URL = "/docs-site/";

export function DocsView() {
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
      <ToolIframe url={DOCS_URL} label="Documentation" />
    </div>
  );
}
