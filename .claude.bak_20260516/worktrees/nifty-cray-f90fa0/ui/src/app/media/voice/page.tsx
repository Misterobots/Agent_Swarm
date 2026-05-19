"use client";

import Link from "next/link";
import { Mic2, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useEffect, useState } from "react";
import { fetchGallery } from "@/lib/api/workspaces";
import type { GalleryItem } from "@/types/workspaces";

export default function MediaVoicePage() {
  const [audioItems, setAudioItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setAudioItems(await fetchGallery("audio"));
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <WorkspaceShell
      title="Media Voice"
      description="Voice artifact generation and media-oriented audio workflows."
      icon={Mic2}
    >
      <WorkspaceSection title="Voice Artifact Surface">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-xs text-[var(--chat-muted)]">Recent generated audio artifacts</p>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
            <Link
              href="/training/voice"
              className="rounded-lg border border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/10 px-3 py-2 text-xs text-[var(--chat-accent)]"
            >
              Open Voice Calibration
            </Link>
          </div>
        </div>

        {audioItems.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--chat-muted)]">
            No audio artifacts in delivered_artifacts yet.
          </p>
        ) : (
          <div className="space-y-2">
            {audioItems.map((item) => (
              <div key={item.name} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-[var(--chat-text)]">{item.name}</p>
                    <p className="text-xs text-[var(--chat-muted)]">
                      {item.size_mb.toFixed(2)} MB · {new Date(item.updated_at * 1000).toLocaleString()}
                    </p>
                  </div>
                  <a href={item.url} download={item.name} className="text-xs text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)]">
                    Download
                  </a>
                </div>
                <audio src={item.url} controls className="mt-2 w-full" />
              </div>
            ))}
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}