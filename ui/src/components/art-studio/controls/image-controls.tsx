"use client";

import { useArtStore } from "@/lib/stores/art-store";

const SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"];
const SCHEDULERS = ["normal", "karras", "simple", "sgm_uniform"];
const ASPECTS = [
  { label: "1:1 Square", w: 1024, h: 1024 },
  { label: "16:9 Cinematic", w: 1344, h: 768 },
  { label: "9:16 Portrait", w: 768, h: 1344 },
];

// Klein-backed quality tiers. These are always available (Klein runs locally
// on Lovelace, no ComfyUI checkpoint required) and they're the only path
// that actually fits FLUX on this hardware. Listed before any ComfyUI
// checkpoints so they're the obvious first pick.
const KLEIN_OPTIONS = [
  { value: "auto",              label: "Auto (Fast — FLUX Schnell, ~10s)" },
  { value: "flux-dev-quality",  label: "FLUX Dev (Quality, ~55s)" },
];

export function ImageControls({ models }: { models: string[] }) {
  const { imageSettings, setImageSettings } = useArtStore();

  const currentAspect = ASPECTS.find(
    (a) => a.w === imageSettings.width && a.h === imageSettings.height
  ) || ASPECTS[0];

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider">
        Image Settings
      </h3>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">Model</span>
        <select
          value={imageSettings.model}
          onChange={(e) => setImageSettings({ model: e.target.value })}
          className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
        >
          <optgroup label="FLUX (Klein dual-GPU)">
            {KLEIN_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </optgroup>
          {models.length > 0 && (
            <optgroup label="ComfyUI checkpoints">
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </optgroup>
          )}
        </select>
        <p className="mt-2 text-xs text-[var(--chat-muted)]">
          {imageSettings.model === "flux-dev-quality"
            ? "First Dev request after Schnell costs ~40s extra for the variant swap."
            : "Schnell is distilled for 4 steps; the steps/CFG sliders below get clamped to schnell-safe values."}
        </p>
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="text-xs text-[var(--chat-muted)]">CFG Scale</span>
          <input
            type="range"
            min={1} max={20} step={0.5}
            value={imageSettings.cfg}
            onChange={(e) => setImageSettings({ cfg: parseFloat(e.target.value) })}
            className="w-full mt-1 accent-violet-500"
          />
          <span className="text-xs text-[var(--chat-muted)]">{imageSettings.cfg}</span>
        </label>
        <label className="block">
          <span className="text-xs text-[var(--chat-muted)]">Steps</span>
          <input
            type="range"
            min={1} max={50} step={1}
            value={imageSettings.steps}
            onChange={(e) => setImageSettings({ steps: parseInt(e.target.value) })}
            className="w-full mt-1 accent-violet-500"
          />
          <span className="text-xs text-[var(--chat-muted)]">{imageSettings.steps}</span>
        </label>
      </div>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">Aspect Ratio</span>
        <select
          value={`${currentAspect.w}x${currentAspect.h}`}
          onChange={(e) => {
            const [w, h] = e.target.value.split("x").map(Number);
            setImageSettings({ width: w, height: h });
          }}
          className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
        >
          {ASPECTS.map((a) => (
            <option key={`${a.w}x${a.h}`} value={`${a.w}x${a.h}`}>
              {a.label} ({a.w}x{a.h})
            </option>
          ))}
        </select>
      </label>

      <details className="group">
        <summary className="text-xs text-[var(--chat-muted)] cursor-pointer hover:text-[var(--chat-text)] transition-colors">
          Advanced Settings
        </summary>
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-[var(--chat-muted)]">Sampler</span>
              <select
                value={imageSettings.sampler}
                onChange={(e) => setImageSettings({ sampler: e.target.value })}
                className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-xs text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
              >
                {SAMPLERS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-[var(--chat-muted)]">Scheduler</span>
              <select
                value={imageSettings.scheduler}
                onChange={(e) => setImageSettings({ scheduler: e.target.value })}
                className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-xs text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
              >
                {SCHEDULERS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <label className="block">
            <span className="text-xs text-[var(--chat-muted)]">Seed (-1 = random)</span>
            <input
              type="number"
              value={imageSettings.seed}
              onChange={(e) => setImageSettings({ seed: parseInt(e.target.value) || -1 })}
              className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
            />
          </label>
        </div>
      </details>
    </div>
  );
}
