"use client";

import { ExternalLink, Download } from "lucide-react";
import type { DesignArtifact } from "@/types/chat";

interface DesignArtifactCardProps {
  artifact: DesignArtifact;
}

export function DesignArtifactCard({ artifact }: DesignArtifactCardProps) {
  const handleDownload = () => {
    const blob = new Blob([artifact.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.filename ?? "design.html";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mt-3 rounded-lg border border-purple-500/30 bg-purple-950/20 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-purple-500/20">
        <span className="text-xs font-medium text-purple-300">
          🎨 Design Artifact
          {artifact.skill && (
            <span className="ml-2 opacity-60">({artifact.skill})</span>
          )}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleDownload}
            className="inline-flex items-center gap-1 text-xs text-purple-400 hover:text-purple-200 transition-colors"
            title="Download HTML"
          >
            <Download size={12} />
            Download
          </button>
          {artifact.project_url && (
            <a
              href={artifact.project_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-purple-400 hover:text-purple-200 transition-colors"
            >
              <ExternalLink size={12} />
              Open Studio
            </a>
          )}
        </div>
      </div>
      <iframe
        srcDoc={artifact.html}
        sandbox="allow-scripts"
        className="w-full h-96 bg-white"
        title="Design Preview"
      />
    </div>
  );
}
