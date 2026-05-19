"use client";

import { Download } from "lucide-react";
import type { MediaAttachment } from "@/types/chat";
import { useState } from "react";

interface MediaPreviewProps {
  media: MediaAttachment;
}

export function MediaPreview({ media }: MediaPreviewProps) {
  const [imageError, setImageError] = useState(false);

  const handleDownload = () => {
    window.open(media.downloadUrl, "_blank");
  };

  // Image preview
  if (media.mimeType.startsWith("image/") && media.previewable && !imageError) {
    return (
      <div className="relative group max-w-md my-3 rounded-lg overflow-hidden border border-[var(--chat-border)] bg-[var(--chat-panel)]">
        <img
          src={media.url}
          alt={media.filename}
          className="w-full h-auto"
          onError={() => setImageError(true)}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 p-3 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-white text-xs font-medium truncate flex-1 mr-2">
            {media.filename}
          </span>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 backdrop-blur-sm rounded-md text-white text-xs font-medium transition-colors pointer-events-auto"
            title="Download"
          >
            <Download size={14} />
            Download
          </button>
        </div>
        {media.width && media.height && (
          <div className="absolute top-2 right-2 px-2 py-1 bg-black/60 backdrop-blur-sm rounded text-white text-[10px] font-medium opacity-0 group-hover:opacity-100 transition-opacity">
            {media.width} × {media.height}
          </div>
        )}
      </div>
    );
  }

  // Video preview
  if (media.mimeType.startsWith("video/") && media.previewable) {
    return (
      <div className="relative max-w-2xl my-3 rounded-lg overflow-hidden border border-[var(--chat-border)] bg-[var(--chat-panel)]">
        <video
          src={media.url}
          controls
          className="w-full h-auto"
          preload="metadata"
        >
          Your browser does not support the video tag.
        </video>
        <div className="p-2 flex items-center justify-between bg-[var(--chat-surface)]">
          <span className="text-[var(--chat-text)] text-xs font-medium truncate flex-1 mr-2">
            {media.filename}
          </span>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--chat-accent)]/10 hover:bg-[var(--chat-accent)]/20 rounded-md text-[var(--chat-accent)] text-xs font-medium transition-colors"
            title="Download"
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </div>
    );
  }

  // Audio preview
  if (media.mimeType.startsWith("audio/") && media.previewable) {
    return (
      <div className="max-w-md my-3 p-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]">
        <audio
          src={media.url}
          controls
          className="w-full"
          preload="metadata"
        >
          Your browser does not support the audio tag.
        </audio>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[var(--chat-text)] text-xs font-medium truncate flex-1 mr-2">
            {media.filename}
          </span>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--chat-accent)]/10 hover:bg-[var(--chat-accent)]/20 rounded-md text-[var(--chat-accent)] text-xs font-medium transition-colors"
            title="Download"
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </div>
    );
  }

  // 3D model preview (GLB/GLTF) - Simple download for now
  // Could be enhanced with a 3D viewer in the future
  if (media.mimeType.includes("gltf") || media.mimeType.includes("model")) {
    return (
      <div className="max-w-md my-3 p-4 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]">
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-[var(--chat-accent)]/10 flex items-center justify-center">
            <svg
              className="w-6 h-6 text-[var(--chat-accent)]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5"
              />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[var(--chat-text)] text-sm font-medium truncate">
              {media.filename}
            </p>
            <p className="text-[var(--chat-muted)] text-xs">
              3D Model • {(media.size / 1024).toFixed(1)} KB
            </p>
          </div>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-2 bg-[var(--chat-accent)]/10 hover:bg-[var(--chat-accent)]/20 rounded-md text-[var(--chat-accent)] text-xs font-medium transition-colors"
            title="Download"
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </div>
    );
  }

  // Generic file download (non-previewable)
  return (
    <div className="max-w-md my-3 p-4 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]">
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-[var(--chat-accent)]/10 flex items-center justify-center">
          <svg
            className="w-6 h-6 text-[var(--chat-accent)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[var(--chat-text)] text-sm font-medium truncate">
            {media.filename}
          </p>
          <p className="text-[var(--chat-muted)] text-xs">
            {(media.size / 1024).toFixed(1)} KB
          </p>
        </div>
        <button
          type="button"
          onClick={handleDownload}
          className="flex items-center gap-1.5 px-3 py-2 bg-[var(--chat-accent)]/10 hover:bg-[var(--chat-accent)]/20 rounded-md text-[var(--chat-accent)] text-xs font-medium transition-colors"
          title="Download"
        >
          <Download size={14} />
          Download
        </button>
      </div>
    </div>
  );
}
