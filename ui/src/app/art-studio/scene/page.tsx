"use client";

import { useState } from "react";
import { SceneCardGrid } from "@/components/scene/scene-card-grid";
import { startScene } from "@/lib/api/scene";

export default function SceneComposerPage() {
  const [prompt, setPrompt] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleStart = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const res = await startScene(prompt, "omnigen");
      setJobId(res.job_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-[var(--chat-text)]">Scene Composer</h1>
        <p className="text-sm text-[var(--chat-muted)]">
          For long, multi-character scenes. Decomposes into establishing shot + hero shots,
          generates each via FLUX dev, then composes them with OmniGen2.
        </p>
      </header>

      <textarea
        rows={10}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Paste your full narrative scene description (settings, characters, action, mood)…"
        className="w-full p-3 rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] text-sm text-[var(--chat-text)] font-mono"
      />

      <div className="flex items-center justify-between">
        <span className="text-[11px] text-[var(--chat-muted)]">
          {prompt.length} chars
          {prompt.length < 1800 && <span className="text-amber-400 ml-2">· (decomposition triggers at ≥1800 chars)</span>}
        </span>
        <button
          disabled={submitting || prompt.length < 1800}
          onClick={handleStart}
          className="text-sm font-semibold px-4 py-1.5 rounded bg-[var(--chat-accent)] text-black hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? "Submitting…" : "Decompose & Generate"}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded border border-red-500/40 bg-red-500/10 text-sm text-red-300">
          {error}
        </div>
      )}

      {jobId && <SceneCardGrid jobId={jobId} />}
    </div>
  );
}
