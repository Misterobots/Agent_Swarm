"use client";

import { useState } from "react";
import { ExternalLink, Download, Hammer, CheckCircle } from "lucide-react";
import type { DesignArtifact } from "@/types/chat";
import { useSettingsStore } from "@/lib/stores/settings-store";

interface DesignArtifactCardProps {
  artifact: DesignArtifact;
  /** Called when the user approves the design and wants to kick off Swarm build */
  onSend?: (message: string) => void;
}

export function DesignArtifactCard({ artifact, onSend }: DesignArtifactCardProps) {
  const [approved, setApproved] = useState(false);
  const setSwarmMode   = useSettingsStore((s) => s.setSwarmMode);
  const setDesignMode  = useSettingsStore((s) => s.setDesignMode);
  const setWorkshopMode = useSettingsStore((s) => s.setWorkshopMode);

  const handleDownload = () => {
    const blob = new Blob([artifact.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.filename ?? "design.html";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleApproveBuild = () => {
    if (!onSend || approved) return;
    setApproved(true);
    setWorkshopMode(false);
    setDesignMode(false);
    setSwarmMode(true);

    const filename = artifact.filename ?? `design_${artifact.project_id}.html`;
    const prompt = [
      `Implement this project as a complete, fully working application.`,
      ``,
      `Approved UI reference: /workspace/delivered_artifacts/${filename}`,
      ``,
      `Steps:`,
      `1. Load the reference file with read_file() — it is the approved UI specification`,
      `2. Implement all screens, navigation flows, and interactions from the reference`,
      `3. Match colours, typography, and layout from the reference file exactly`,
      `4. Ship a fully functional application — not another static HTML file`,
    ].join("\n");

    onSend(prompt);
  };

  const borderColor = approved ? "border-emerald-500/50" : "border-purple-500/30";
  const bgColor     = approved ? "bg-emerald-950/20"     : "bg-purple-950/20";
  const headerBorder = approved ? "border-emerald-500/30" : "border-purple-500/20";

  return (
    <div className={`mt-3 rounded-lg border ${borderColor} ${bgColor} overflow-hidden transition-colors duration-500`}>
      {/* Header */}
      <div className={`flex items-center justify-between px-3 py-2 border-b ${headerBorder}`}>
        <span className={`text-xs font-medium ${approved ? "text-emerald-300" : "text-purple-300"}`}>
          {approved ? "✅ Design Approved" : "🎨 Design Artifact"}
          {artifact.skill && !approved && (
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

          {onSend && (
            <button
              type="button"
              onClick={handleApproveBuild}
              disabled={approved}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                approved
                  ? "bg-emerald-700/40 text-emerald-300 cursor-default"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm hover:shadow-emerald-500/25"
              }`}
              title="Approve this design and start building"
            >
              {approved
                ? <><CheckCircle size={12} /> Approved</>
                : <><Hammer size={12} /> Approve &amp; Build</>
              }
            </button>
          )}
        </div>
      </div>

      {/* Preview */}
      <iframe
        srcDoc={artifact.html}
        sandbox="allow-scripts"
        className="w-full h-96 bg-white"
        title="Design Preview"
      />
    </div>
  );
}
