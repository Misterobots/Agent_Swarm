"use client";

import { Hammer, RefreshCw, CheckCircle2 } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { fetchComfyStatus, fetchGallery, generateCreatureForge } from "@/lib/api/workspaces";
import type { GalleryItem } from "@/types/workspaces";
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
  const [selectedImage, setSelectedImage] = useState<GalleryItem | null>(null);
  const [workflowName, setWorkflowName] = useState(WORKFLOWS[0].name);
  const [comfyOnline, setComfyOnline] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState("");
  const [imageGallery, setImageGallery] = useState<GalleryItem[]>([]);
  const [recentMedia, setRecentMedia] = useState<Array<{ name: string; url: string; updated_at: number }>>([]);
  const [galleryLoading, setGalleryLoading] = useState(true);

  async function load() {
    const [status, images, all] = await Promise.all([
      fetchComfyStatus(),
      fetchGallery("image"),
      fetchGallery("all"),
    ]);
    setComfyOnline(Boolean(status?.healthy));
    setImageGallery(images);
    setGalleryLoading(false);

    const modelArtifacts = all
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

  function selectGalleryImage(item: GalleryItem) {
    setSelectedImage(item);
    setImagePath(`/workspace/delivered_artifacts/${item.name}`);
  }

  async function generate() {
    const path = imagePath.trim();
    if (!path) return;
    setGenerating(true);
    setResult("Queueing Creature Forge...");

    const response = await generateCreatureForge({ image_path: path, workflow_name: workflowName });
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
      <WorkspaceSection title="Select Source Image">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs text-[var(--chat-muted)]">Pick from your delivered image artifacts</p>
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} className={galleryLoading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        {galleryLoading ? (
          <p className="py-6 text-center text-sm text-[var(--chat-muted)]">Loading image gallery...</p>
        ) : imageGallery.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--chat-muted)]">
            No image artifacts found. Generate images in Studio first, then return here.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {imageGallery.map((item) => {
              const isSelected = selectedImage?.name === item.name;
              return (
                <button
                  key={item.name}
                  onClick={() => selectGalleryImage(item)}
                  className={`group relative overflow-hidden rounded-lg border text-left transition-all ${
                    isSelected
                      ? "border-[var(--chat-accent)] ring-1 ring-[var(--chat-accent)]"
                      : "border-[var(--chat-border)] hover:border-[var(--chat-accent)]/50"
                  }`}
                >
                  <img
                    src={item.url}
                    alt={item.name}
                    className="h-32 w-full object-cover"
                    loading="lazy"
                  />
                  {isSelected && (
                    <div className="absolute inset-0 flex items-center justify-center bg-[var(--chat-accent)]/20">
                      <CheckCircle2 size={28} className="text-[var(--chat-accent)]" />
                    </div>
                  )}
                  <div className="p-2">
                    <p className="truncate text-[11px] text-[var(--chat-muted)]">{item.name}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {selectedImage && (
          <p className="mt-3 text-xs text-[var(--chat-accent)]">
            Selected: <span className="font-mono">{selectedImage.name}</span>
          </p>
        )}
      </WorkspaceSection>

      <WorkspaceSection title="Run Conversion">
        <div className="grid gap-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">
              Source Image Path
              <span className="ml-2 text-[var(--chat-subtle)]">(auto-filled from selection above, or enter manually)</span>
            </label>
            <input
              value={imagePath}
              onChange={(e) => { setImagePath(e.target.value); setSelectedImage(null); }}
              placeholder="/workspace/delivered_artifacts/ComfyUI_00001.png"
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

          {result && (
            <p className="md:col-span-2 rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-text)]">
              {result}
            </p>
          )}
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
          <p className="py-8 text-center text-sm text-[var(--chat-muted)]">No 3D artifacts detected yet.</p>
        ) : (
          <div className="space-y-2">
            {recentMedia.map((item) => (
              <div key={item.name} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-[var(--chat-text)]">{item.name}</p>
                    <p className="text-xs text-[var(--chat-muted)]">{new Date(item.updated_at * 1000).toLocaleString()}</p>
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
