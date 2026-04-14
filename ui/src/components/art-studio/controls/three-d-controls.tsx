"use client";

import { useArtStore } from "@/lib/stores/art-store";

const WORKFLOWS = [
  { label: "TripoSG (Fast, ~2 min)", value: "workflow_triposg.json" },
  { label: "Hunyuan 3D (Textured, ~8 min)", value: "workflow_hunyuan_paint.json" },
];

const QUALITY_OPTS = [
  { label: "Fast (~50 steps)", value: "fast" as const },
  { label: "Balanced (~75 steps)", value: "balanced" as const },
  { label: "High (~100 steps)", value: "high" as const },
];

const ADHERENCE_OPTS = [
  { label: "Low (more creative)", value: "low" as const },
  { label: "Medium", value: "medium" as const },
  { label: "High (strict to source)", value: "high" as const },
];

export function ThreeDControls() {
  const { threeDSettings, setThreeDSettings } = useArtStore();

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider">
        3D Generation
      </h3>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">Pipeline</span>
        <select
          value={threeDSettings.workflow}
          onChange={(e) => setThreeDSettings({ workflow: e.target.value })}
          className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
        >
          {WORKFLOWS.map((w) => (
            <option key={w.value} value={w.value}>{w.label}</option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">Quality</span>
        <select
          value={threeDSettings.quality}
          onChange={(e) => setThreeDSettings({ quality: e.target.value as "fast" | "balanced" | "high" })}
          className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
        >
          {QUALITY_OPTS.map((q) => (
            <option key={q.value} value={q.value}>{q.label}</option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">Source Adherence</span>
        <select
          value={threeDSettings.sourceAdherence}
          onChange={(e) => setThreeDSettings({ sourceAdherence: e.target.value as "low" | "medium" | "high" })}
          className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
        >
          {ADHERENCE_OPTS.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
      </label>

      <p className="text-xs text-[var(--chat-muted)]">
        Quality controls inference steps. Source adherence controls how closely
        the 3D geometry follows the input image (higher = stricter match).
      </p>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={threeDSettings.autoConcept}
          onChange={(e) => setThreeDSettings({ autoConcept: e.target.checked })}
          className="rounded border-[var(--chat-border)] bg-[var(--chat-panel)] text-violet-500 focus:ring-violet-500"
        />
        <span className="text-xs text-[var(--chat-muted)]">Auto-generate concept art first</span>
      </label>

      <p className="text-xs text-[var(--chat-muted)]">
        When enabled, the system creates optimized concept art from your prompt
        before converting to 3D. The image is preprocessed with background
        removal for cleaner geometry.
      </p>
    </div>
  );
}
