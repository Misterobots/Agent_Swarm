"use client";

import { ImagePlus, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { fetchGallery } from "@/lib/api/workspaces";
import type { GalleryItem } from "@/types/workspaces";
import { useEffect, useState } from "react";

export default function MediaImagesPage() {
  const [images, setImages] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const items = await fetchGallery("image");
    setImages(items);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <WorkspaceShell
      title="Media Images"
      description="Image generation controls and delivered artifact gallery."
      icon={ImagePlus}
    >
      <WorkspaceSection title="Delivered Artifact Gallery">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-xs text-[var(--chat-muted)]">
            Source: <span className="font-mono">/workspace/delivered_artifacts</span>
          </p>
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        {loading && images.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--chat-muted)]">Loading image artifacts...</p>
        ) : images.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--chat-muted)]">
            No image artifacts found yet. Generate images to populate this gallery.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {images.map((item) => {
              const params = (item.metadata?.params as Record<string, unknown> | undefined) ?? {};
              return (
                <article key={item.name} className="overflow-hidden rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]">
                  <img
                    src={item.url}
                    alt={item.name}
                    className="h-48 w-full object-cover"
                    loading="lazy"
                  />
                  <div className="space-y-1 p-3">
                    <p className="truncate text-sm font-medium text-[var(--chat-text)]">{item.name}</p>
                    <p className="text-xs text-[var(--chat-muted)]">
                      {(item.size_mb ?? 0).toFixed(2)} MB · {new Date(item.updated_at * 1000).toLocaleString()}
                    </p>
                    {typeof item.metadata?.prompt === "string" && (
                      <p className="line-clamp-2 text-xs text-[var(--chat-muted)]">{item.metadata.prompt}</p>
                    )}
                    {(Boolean(params.cfg) || Boolean(params.steps) || Boolean(item.metadata?.model)) && (
                      <p className="text-xs text-[var(--chat-muted)]">
                        {item.metadata?.model ? `Model: ${String(item.metadata.model)} · ` : ""}
                        {params.cfg ? `CFG: ${String(params.cfg)} · ` : ""}
                        {params.steps ? `Steps: ${String(params.steps)}` : ""}
                      </p>
                    )}
                    <a
                      href={item.url}
                      download={item.name}
                      className="inline-block pt-1 text-xs text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)]"
                    >
                      Download
                    </a>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}