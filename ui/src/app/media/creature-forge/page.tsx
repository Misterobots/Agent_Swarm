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
        <div className="grid gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-zinc-400">Source Image Path</label>
            <input
              value={imagePath}
              onChange={(e) => setImagePath(e.target.value)}
              placeholder="/workspace/delivered_artifacts/ComfyUI_action_figure_001.png"
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-zinc-400">Workflow Template</label>
            <select
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200"
            >
              {WORKFLOWS.map((workflow) => (
                <option key={workflow.name} value={workflow.name}>
                  {workflow.label}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-zinc-500">
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

          {result && <p className="md:col-span-2 rounded bg-zinc-950 px-3 py-2 text-xs text-zinc-300">{result}</p>}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Workflow Catalog">
        <div className="grid gap-3 md:grid-cols-3">
          {WORKFLOWS.map((workflow) => (
            <div key={workflow.name} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
              <p className="text-sm font-medium text-zinc-200">{workflow.label}</p>
              <p className="mt-1 text-xs text-zinc-500">{workflow.description}</p>
              <code className="mt-2 block rounded bg-zinc-950 px-2 py-1 text-[11px] text-zinc-400">{workflow.name}</code>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Recent 3D Artifacts">
        <div className="mb-3 flex justify-end">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-400 hover:text-zinc-200"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {recentMedia.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-500">No 3D artifacts detected in delivered artifacts yet.</p>
        ) : (
          <div className="space-y-2">
            {recentMedia.map((item) => (
              <div key={item.name} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-zinc-200">{item.name}</p>
                    <p className="text-xs text-zinc-500">{new Date(item.updated_at * 1000).toLocaleString()}</p>
                  </div>
                  <a href={item.url} download={item.name} className="text-xs text-[var(--chat-accent)]">
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
