"use client";

import { Hammer, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { fetchComfyStatus, fetchGallery, generateCreatureForge } from "@/lib/api/workspaces";
import { useEffect, useState } from "react";

const WORKFLOWS = [
  {
    name: "workflow_hunyuan_paint-2.json",
    label: "Hunyuan Paint v2",
    description: "Delight + TripoSG + Instant Remesh + Paint + Bake texture",
  },
  {
    name: "workflow_hunyuan_paint.json",
    label: "Hunyuan Paint",
    description: "TripoSG pipeline with Hunyuan paint and texture transfer",
  },
  {
    name: "workflow_triposg.json",
    label: "TripoSG Base",
    description: "Fast 2D to 3D conversion with TripoSG defaults",
  },
];

export default function CreatureForgePage() {
  const [imagePath, setImagePath] = useState("");
  const [workflowName, setWorkflowName] = useState(WORKFLOWS[0].name);
  const [comfyOnline, setComfyOnline] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState("");
  const [recentMedia, setRecentMedia] = useState<Array<{ name: string; url: string; updated_at: number }>>([]);

  async function load() {
    const [status, gallery] = await Promise.all([fetchComfyStatus(), fetchGallery("all")]);
    setComfyOnline(Boolean(status?.healthy));

    const modelArtifacts = gallery
      .filter((item) => {
        const ext = item.name.toLowerCase();
        return ext.endsWith(".glb") || ext.endsWith(".obj") || ext.endsWith(".3mf");
      })
      .map((item) => ({ name: item.name, url: item.url, updated_at: item.updated_at }));

    setRecentMedia(modelArtifacts.slice(0, 20));
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!imagePath.trim()) return;
    setGenerating(true);
    setResult("Queueing Creature Forge...");

    const response = await generateCreatureForge({ image_path: imagePath.trim(), workflow_name: workflowName });
    setResult(response?.result ?? "Creature Forge failed");
    setGenerating(false);
    await load();
  }

  return (
    <WorkspaceShell
      title="Creature Forge"
      description="Convert 2D concept art into 3D assets using TripoSG and Hunyuan Paint workflows."
      icon={Hammer}
    >
      <WorkspaceSection title="2D to 3D Conversion">
        <div className="grid gap-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Source Image Path</label>
            <input
              value={imagePath}
              onChange={(e) => setImagePath(e.target.value)}
              placeholder="/workspace/delivered_artifacts/ComfyUI_action_figure_001.png"
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Workflow Template</label>
            <select
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            >
              {WORKFLOWS.map((workflow) => (
                <option key={workflow.name} value={workflow.name}>
                  {workflow.label}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-[var(--chat-muted)]">
              {WORKFLOWS.find((w) => w.name === workflowName)?.description}
            </p>
          </div>

          <div className="flex items-end justify-between">
            <p className={`text-xs ${comfyOnline ? "text-emerald-400" : "text-red-400"}`}>
              ComfyUI: {comfyOnline ? "Online" : "Offline"}
            </p>
            <button
              onClick={generate}
              disabled={generating || !imagePath.trim()}
              className="rounded border border-[var(--chat-accent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_16%,transparent)] px-3 py-2 text-sm text-[var(--chat-accent)] disabled:opacity-50"
            >
              {generating ? "Forging..." : "Run Creature Forge"}
            </button>
          </div>

          {result && <p className="md:col-span-2 rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-text)]">{result}</p>}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Workflow Catalog">
        <div className="grid gap-3 md:grid-cols-3">
          {WORKFLOWS.map((workflow) => (
            <div key={workflow.name} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
              <p className="text-sm font-medium text-[var(--chat-text)]">{workflow.label}</p>
              <p className="mt-1 text-xs text-[var(--chat-muted)]">{workflow.description}</p>
              <code className="mt-2 block rounded bg-[var(--chat-bg)] px-2 py-1 text-[11px] text-[var(--chat-muted)]">{workflow.name}</code>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Recent 3D Artifacts">
        <div className="mb-3 flex justify-end">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {recentMedia.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--chat-muted)]">No 3D artifacts detected in delivered artifacts yet.</p>
        ) : (
          <div className="space-y-2">
            {recentMedia.map((item) => (
              <div key={item.name} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-[var(--chat-text)]">{item.name}</p>
                    <p className="text-xs text-[var(--chat-muted)]">{new Date(item.updated_at * 1000).toLocaleString()}</p>
                  </div>
                  <a href={item.download_url || item.url} download={item.name} className="text-xs text-[var(--chat-accent)]">
                    Download
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
