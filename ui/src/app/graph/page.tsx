"use client";

import { useState, useRef, useEffect } from "react";
import { Network, Brain, RefreshCw, ExternalLink } from "lucide-react";
import { useAccess } from "@/lib/hooks/use-access";

// ── Tab config ────────────────────────────────────────────────────────────────

type TabId = "memory" | "codebase";

interface TabDef {
  id: TabId;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  description: string;
  getUrl: (uid: string | null) => string;
}

const TABS: TabDef[] = [
  {
    id: "memory",
    label: "Memory Graph",
    icon: Brain,
    description: "Entities and relationships extracted from your AI conversations",
    getUrl: (uid) =>
      `/api/backend/v1/palace/graph?mode=entity&format=html${uid ? `&owner_id=${encodeURIComponent(uid)}` : ""}`,
  },
  {
    id: "codebase",
    label: "Codebase Graph",
    icon: Network,
    description: "Code structure, documentation concepts, and cross-file relationships",
    getUrl: () => `/api/backend/v1/graph/codebase?fmt=html`,
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function GraphPage() {
  const [activeTab, setActiveTab] = useState<TabId>("memory");
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { uid, username } = useAccess();

  // Use uid if available, fall back to username
  const ownerId = uid || username;

  const activeTabDef = TABS.find((t) => t.id === activeTab)!;
  const iframeUrl = activeTabDef.getUrl(ownerId);

  // Reset loading state on tab or reload change
  useEffect(() => {
    setLoading(true);
  }, [activeTab, reloadKey]);

  function handleTabChange(id: TabId) {
    if (id !== activeTab) {
      setActiveTab(id);
    }
  }

  function handleReload() {
    setReloadKey((k) => k + 1);
  }

  function handleOpenExternal() {
    window.open(iframeUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div
      className="flex flex-col h-full w-full"
      style={{ background: "var(--chat-bg)" }}
    >
      {/* ── Header bar ── */}
      <div
        className="flex-shrink-0 flex items-center gap-3 px-4 py-2.5 border-b"
        style={{ borderColor: "var(--chat-border)", background: "var(--chat-surface)" }}
      >
        {/* Tab pills */}
        <div className="flex items-center gap-1 flex-1 min-w-0">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
                style={{
                  background: active ? "var(--chat-accent-soft)" : "transparent",
                  color: active ? "var(--chat-accent-strong)" : "var(--chat-muted)",
                  border: active
                    ? "1px solid color-mix(in srgb, var(--chat-accent) 30%, var(--chat-border))"
                    : "1px solid transparent",
                }}
                title={tab.description}
              >
                <Icon size={14} className="shrink-0" />
                <span>{tab.label}</span>
              </button>
            );
          })}

          {/* Description */}
          <span
            className="ml-3 text-xs truncate hidden md:block"
            style={{ color: "var(--chat-subtle)" }}
          >
            {activeTabDef.description}
          </span>
        </div>

        {/* Loading indicator */}
        {loading && (
          <div
            className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0"
            style={{ background: "var(--chat-accent)" }}
            title="Loading graph…"
          />
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={handleReload}
            className="w-7 h-7 flex items-center justify-center rounded-md transition-colors"
            style={{ color: "var(--chat-subtle)" }}
            title="Reload graph"
          >
            <RefreshCw size={13} />
          </button>
          <button
            onClick={handleOpenExternal}
            className="w-7 h-7 flex items-center justify-center rounded-md transition-colors"
            style={{ color: "var(--chat-subtle)" }}
            title="Open in new tab"
          >
            <ExternalLink size={13} />
          </button>
        </div>
      </div>

      {/* ── Graph iframe ── */}
      {/* One iframe per tab, hidden when not active — preserves scroll/zoom state */}
      {TABS.map((tab) => (
        <iframe
          key={`${tab.id}-${reloadKey}`}
          ref={tab.id === activeTab ? iframeRef : undefined}
          src={tab.getUrl(ownerId)}
          className="flex-1 w-full border-0"
          style={{ display: tab.id === activeTab ? "block" : "none" }}
          title={tab.label}
          onLoad={() => {
            if (tab.id === activeTab) setLoading(false);
          }}
          // Allow full interaction within the iframe
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      ))}
    </div>
  );
}
