"use client";

import { Sparkles, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import {
  fetchComfyCheckpoints,
  fetchComfyStatus,
  fetchGallery,
  generateActionFigure,
} from "@/lib/api/workspaces";
import type { GalleryItem } from "@/types/workspaces";
import { useEffect, useState } from "react";

const SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_2m_sde"];
const SCHEDULERS = ["normal", "karras", "simple"];

export default function ActionFigurePage() {
  const [prompt, setPrompt] = useState("");
  const [modelName, setModelName] = useState("auto");
  const [cfg, setCfg] = useState(7);
  const [steps, setSteps] = useState(20);
  const [sampler, setSampler] = useState("euler");
  const [scheduler, setScheduler] = useState("normal");

  const [models, setModels] = useState<string[]>(["auto"]);
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [comfyOnline, setComfyOnline] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<string>("");

  async function load() {
    const [status, checkpoints, images] = await Promise.all([
      fetchComfyStatus(),
      fetchComfyCheckpoints(),
      fetchGallery("image"),
    ]);

    setComfyOnline(Boolean(status?.healthy));
    setModels(["auto", ...(checkpoints.models || [])]);
    setGallery(
      images.filter((item) => {
        const promptMeta = String(item.metadata?.prompt || "").toLowerCase();
        return promptMeta.includes("action figure") || promptMeta.includes("collectible toy");
      })
    );
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!prompt.trim()) return;
    setGenerating(true);
    setResult("Queueing generation...");

    const response = await generateActionFigure({
      prompt,
      model_name: modelName,
      cfg,
      steps,
      sampler,
      scheduler,
    });

    setResult(response?.result ?? "Generation failed");
    setGenerating(false);
    await load();
  }

  return (
    <WorkspaceShell
      title="Action Figure"
      description="Generate collectible action-figure concept art with ComfyUI controls."
      icon={Sparkles}
    >
      <WorkspaceSection title="Generator">
        <div className="grid gap-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Create a sci-fi mech pilot action figure with articulated elbows and premium packaging"
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Checkpoint</label>
            <select
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            >
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">CFG</label>
            <input
              type="number"
              min={1}
              max={20}
              step={0.5}
              value={cfg}
              onChange={(e) => setCfg(Number(e.target.value))}
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Steps</label>
            <input
              type="number"
              min={2}
              max={80}
              value={steps}
              onChange={(e) => setSteps(Number(e.target.value))}
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Sampler</label>
            <select
              value={sampler}
              onChange={(e) => setSampler(e.target.value)}
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            >
              {SAMPLERS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-[var(--chat-muted)]">Scheduler</label>
            <select
              value={scheduler}
              onChange={(e) => setScheduler(e.target.value)}
              className="w-full rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            >
              {SCHEDULERS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2 flex items-center justify-between gap-3">
            <p className={`text-xs ${comfyOnline ? "text-emerald-400" : "text-red-400"}`}>
              ComfyUI: {comfyOnline ? "Online" : "Offline"}
            </p>
            <button
              onClick={generate}
              disabled={generating || !prompt.trim()}
              className="rounded border border-[var(--chat-accent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_16%,transparent)] px-3 py-2 text-sm text-[var(--chat-accent)] disabled:opacity-50"
            >
              {generating ? "Generating..." : "Generate Action Figure"}
            </button>
          </div>

          {result && <p className="md:col-span-2 rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-text)]">{result}</p>}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Recent Action Figure Results">
        <div className="mb-3 flex justify-end">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {gallery.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--chat-muted)]">No action-figure artifacts found yet.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {gallery.map((item) => (
              <article key={item.name} className="overflow-hidden rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]">
                <img src={item.url} alt={item.name} className="h-48 w-full object-cover" loading="lazy" />
                <div className="space-y-1 p-3">
                  <p className="truncate text-sm font-medium text-[var(--chat-text)]">{item.name}</p>
                  <p className="text-xs text-[var(--chat-muted)]">{new Date(item.updated_at * 1000).toLocaleString()}</p>
                  <a href={item.download_url || item.url} download={item.name} className="inline-block text-xs text-[var(--chat-accent)]">
                    Download
                  </a>
                </div>
              </article>
            ))}
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
