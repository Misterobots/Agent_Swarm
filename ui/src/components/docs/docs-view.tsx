"use client";

import { useState, useEffect, useCallback } from "react";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import { BookOpen, User, Shield, ChevronRight, Loader2 } from "lucide-react";

type Audience = "user" | "admin";

interface DocEntry {
  label: string;
  key: string;
}

const USER_DOCS: DocEntry[] = [
  { label: "System Overview", key: "user/overview" },
  { label: "How It Works", key: "user/framework" },
  { label: "FAQ", key: "user/faq" },
];

const ADMIN_DOCS: DocEntry[] = [
  { label: "Design Framework", key: "admin/design_framework" },
  { label: "Technical Reference", key: "admin/technical_reference" },
  { label: "Security", key: "admin/security" },
  { label: "Troubleshooting", key: "admin/troubleshooting" },
];

export function DocsView() {
  const [audience, setAudience] = useState<Audience>("user");
  const [activeKey, setActiveKey] = useState<string>("user/overview");
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDoc = useCallback(async (key: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/docs?doc=${encodeURIComponent(key)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const text = await res.text();
      setContent(text);
    } catch (e) {
      setError(`Failed to load document: ${e instanceof Error ? e.message : String(e)}`);
      setContent("");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDoc(activeKey);
  }, [activeKey, fetchDoc]);

  const handleAudienceChange = (next: Audience) => {
    setAudience(next);
    const firstDoc = next === "user" ? USER_DOCS[0] : ADMIN_DOCS[0];
    setActiveKey(firstDoc.key);
  };

  const docs = audience === "user" ? USER_DOCS : ADMIN_DOCS;

  return (
    <div className="flex h-full bg-[var(--chat-bg)] text-[var(--chat-text)]">
      {/* Sidebar */}
      <div className="w-56 flex-shrink-0 border-r border-[var(--chat-border)] flex flex-col">
        {/* Audience tabs */}
        <div className="flex border-b border-[var(--chat-border)]">
          <button
            onClick={() => handleAudienceChange("user")}
            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-medium transition-colors ${
              audience === "user"
                ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            }`}
          >
            <User size={13} />
            Users
          </button>
          <button
            onClick={() => handleAudienceChange("admin")}
            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-medium transition-colors ${
              audience === "admin"
                ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            }`}
          >
            <Shield size={13} />
            Admins
          </button>
        </div>

        {/* Doc list */}
        <nav className="flex-1 py-2">
          {docs.map((doc) => (
            <button
              key={doc.key}
              onClick={() => setActiveKey(doc.key)}
              className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors text-left ${
                activeKey === doc.key
                  ? "bg-[var(--chat-panel)] text-[var(--chat-accent)] border-r-2 border-[var(--chat-accent)]"
                  : "text-[var(--chat-muted)] hover:bg-[var(--chat-surface)] hover:text-[var(--chat-text)]"
              }`}
            >
              <span>{doc.label}</span>
              {activeKey === doc.key && <ChevronRight size={13} className="text-[var(--chat-accent)]" />}
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[var(--chat-border)]">
          <div className="flex items-center gap-2 text-[var(--chat-muted)] text-xs">
            <BookOpen size={12} />
            <span>Agentic Hive v3.3</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <Loader2 size={24} className="animate-spin text-[var(--chat-accent)]" />
          </div>
        )}
        {error && !loading && (
          <div className="flex items-center justify-center h-full text-red-400 text-sm">
            {error}
          </div>
        )}
        {!loading && !error && content && (
          <div className="max-w-4xl mx-auto px-8 py-8">
            <MarkdownRenderer content={content} />
          </div>
        )}
      </div>
    </div>
  );
}
