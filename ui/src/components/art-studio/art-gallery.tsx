"use client";

import { useEffect, useState } from "react";
import { fetchImageGallery, fetch3DGallery, type GalleryImage, type Gallery3DFile } from "@/lib/api/art";
import { Image, Box, RefreshCw, Download } from "lucide-react";
import { cn } from "@/lib/utils/cn";

type Tab = "images" | "3d";

export function ArtGallery() {
  const [tab, setTab] = useState<Tab>("images");
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [files3d, setFiles3d] = useState<Gallery3DFile[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    const [imgs, f3d] = await Promise.all([fetchImageGallery(), fetch3DGallery()]);
    setImages(imgs);
    setFiles3d(f3d);
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto">
        {/* Tab bar + refresh */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex gap-1 bg-[var(--chat-panel)] rounded-lg p-1">
            <button
              onClick={() => setTab("images")}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all",
                tab === "images" ? "bg-violet-600 text-white" : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
              )}
            >
              <Image size={14} /> Images ({images.length})
            </button>
            <button
              onClick={() => setTab("3d")}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all",
                tab === "3d" ? "bg-violet-600 text-white" : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
              )}
            >
              <Box size={14} /> 3D Files ({files3d.length})
            </button>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] bg-[var(--chat-panel)] hover:bg-[var(--chat-surface)] transition-colors"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        {/* Image Gallery */}
        {tab === "images" && (
          images.length === 0 ? (
            <p className="text-center text-[var(--chat-muted)] py-20">No images yet. Generate some in the Art Studio!</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {images.map((img) => (
                <div
                  key={img.filename}
                  className="group rounded-xl border border-[var(--chat-border)] bg-[var(--chat-bg)] overflow-hidden hover:border-violet-700/50 transition-colors"
                >
                  <div className="aspect-square bg-[var(--chat-panel)] relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`/api/backend${img.url}`}
                      alt={img.filename}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="p-3">
                    <p className="text-xs text-[var(--chat-muted)] truncate">{img.filename}</p>
                    {"prompt" in img.meta && img.meta.prompt != null && (
                      <p className="text-[10px] text-[var(--chat-muted)] truncate mt-0.5">
                        {String(img.meta.prompt)}
                      </p>
                    )}
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-[10px] text-[var(--chat-muted)]">
                        {(img.size_bytes / 1024).toFixed(0)} KB
                      </span>
                      <a
                        href={`/api/backend${img.url}`}
                        download={img.filename}
                        className="flex items-center gap-1 text-[10px] text-violet-400 hover:text-violet-300"
                      >
                        <Download size={10} /> Download
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {/* 3D Gallery */}
        {tab === "3d" && (
          files3d.length === 0 ? (
            <p className="text-center text-[var(--chat-muted)] py-20">No 3D files yet. Generate some models or action figures!</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {files3d.map((f) => (
                <div
                  key={f.filename}
                  className="rounded-xl border border-[var(--chat-border)] bg-[var(--chat-bg)] p-5 text-center hover:border-violet-700/50 transition-colors"
                >
                  <div className="text-4xl mb-3">
                    {f.category === "action_figures" ? "\uD83E\uDDBE" : "\uD83E\uDDCA"}
                  </div>
                  <p className="text-sm font-medium text-[var(--chat-text)] truncate">{f.filename}</p>
                  <p className="text-xs text-[var(--chat-muted)] mt-1">
                    {f.ext} &bull; {(f.size_bytes / (1024 * 1024)).toFixed(1)} MB
                  </p>
                  <p className="text-[10px] text-[var(--chat-muted)] mt-0.5">{f.category}</p>
                  <a
                    href={`/api/backend${f.download_url}`}
                    download={f.filename}
                    className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-violet-600 hover:bg-violet-500 text-white transition-colors"
                  >
                    <Download size={12} /> Download {f.ext}
                  </a>
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}
