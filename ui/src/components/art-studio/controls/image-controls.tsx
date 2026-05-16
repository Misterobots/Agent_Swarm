"use client";

import { useEffect, useRef } from "react";
import { useArtStore } from "@/lib/stores/art-store";

const SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"];
const SCHEDULERS = ["normal", "karras", "simple", "sgm_uniform"];
const ASPECTS = [
  { label: "1:1 Square", w: 1024, h: 1024 },
  { label: "16:9 Cinematic", w: 1344, h: 768 },
  { label: "9:16 Portrait", w: 768, h: 1344 },
];

// Klein-backed FLUX variants. Both are always available (Klein runs locally
// on Lovelace, no ComfyUI checkpoint required) and they're the only path
// that actually fits FLUX on this hardware.
//
// IMPORTANT: Dev is NOT strictly higher quality than Schnell — it's a
// different model with a different aesthetic prior. A/B testing showed Dev
// shifts toward a "composed/stylized" look while Schnell stays closer to
// literal prompt rendering (better photorealism). Tooltips reflect this
// honest framing so users pick based on the task, not assumed "quality."
// Per-model slider constraints. The backend (image_gen.py) clamps anything
// out of range as a safety net, but the UI shouldn't let users drag into the
// wasted-compute zone in the first place. Each entry mirrors the backend's
// accepted range and recommended default.
type SliderConfig = {
  cfg:   { min: number; max: number; step: number; recommended: number; disabled?: boolean; note?: string };
  steps: { min: number; max: number; step: number; recommended: number };
};
const MODEL_SLIDER_DEFAULTS: SliderConfig = {
  // Generic ComfyUI fallback (SDXL-style). Used when a checkpoint is selected.
  cfg:   { min: 1.0, max: 20.0, step: 0.5, recommended: 7.0 },
  steps: { min: 1, max: 50, step: 1, recommended: 20 },
};
function getSliderConfig(model: string): SliderConfig {
  // Klein FLUX.1-schnell — distilled for 4 steps, ignores CFG.
  if (model === "auto" || model === "klein-9b" || model === "flux-schnell-preview") {
    return {
      cfg:   {
        min: 3.5, max: 3.5, step: 0.5, recommended: 3.5, disabled: true,
        note: "Schnell ignores CFG (flow-matching).",
      },
      steps: { min: 1, max: 4, step: 1, recommended: 4 },
    };
  }
  // Klein FLUX.1-dev — real CFG, 12-30 step sweet spot.
  if (model === "flux-dev-quality") {
    return {
      cfg:   { min: 1.5, max: 7.0, step: 0.5, recommended: 3.5 },
      steps: { min: 12, max: 30, step: 1, recommended: 25 },
    };
  }
  return MODEL_SLIDER_DEFAULTS;
}

const KLEIN_OPTIONS: { value: string; label: string; tooltip: string }[] = [
  {
    value: "auto",
    label: "Auto (FLUX Schnell — fast, ~10s)",
    tooltip:
      "FLUX.1-schnell via Klein dual-GPU. The right default for almost everything: " +
      "photorealism, illustrations, anime, drafts, fast iteration. 4 steps, ~10 seconds. " +
      "Limitation: text in the image will be garbled — use FLUX Dev when text matters.",
  },
  {
    value: "flux-dev-quality",
    label: "FLUX Dev (text-in-image, ~55s)",
    tooltip:
      "FLUX.1-dev via Klein dual-GPU. Pick this specifically when your image needs to contain " +
      "legible text (signs, labels, words) or has complex multi-element composition where Schnell " +
      "gets confused. 25 steps with real CFG. ~55 seconds. First Dev request after Schnell costs " +
      "an extra ~40s for the variant swap. " +
      "Not a general 'quality upgrade' — for plain photoreal or illustration, Schnell is better.",
  },
];

export function ImageControls({ models }: { models: string[] }) {
  const { imageSettings, setImageSettings } = useArtStore();
  const sliderConfig = getSliderConfig(imageSettings.model);

  const currentAspect = ASPECTS.find(
    (a) => a.w === imageSettings.width && a.h === imageSettings.height
  ) || ASPECTS[0];

  // When the user switches model, snap stored slider values into the new model's
  // valid range. Preserves the user's intent when current values are already in
  // range; otherwise jumps to the recommended default for the new model. The ref
  // tracks the previous model so the effect only fires on actual model changes,
  // not every render.
  const prevModelRef = useRef(imageSettings.model);
  useEffect(() => {
    if (prevModelRef.current === imageSettings.model) return;
    prevModelRef.current = imageSettings.model;
    const cfg = imageSettings.cfg;
    const steps = imageSettings.steps;
    const cfgInRange   = cfg   >= sliderConfig.cfg.min   && cfg   <= sliderConfig.cfg.max;
    const stepsInRange = steps >= sliderConfig.steps.min && steps <= sliderConfig.steps.max;
    const patch: Partial<{ cfg: number; steps: number }> = {};
    if (!cfgInRange)   patch.cfg   = sliderConfig.cfg.recommended;
    if (!stepsInRange) patch.steps = sliderConfig.steps.recommended;
    if (patch.cfg !== undefined || patch.steps !== undefined) {
      setImageSettings(patch);
    }
  }, [imageSettings.model, imageSettings.cfg, imageSettings.steps, sliderConfig, setImageSettings]);

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
              <option key={o.value} value={o.value} title={o.tooltip}>{o.label}</option>
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
        {(() => {
          const selected = KLEIN_OPTIONS.find((o) => o.value === imageSettings.model);
          if (selected) {
            return (
              <p className="mt-2 text-xs text-[var(--chat-muted)] leading-relaxed">
                {selected.tooltip}
              </p>
            );
          }
          return (
            <p className="mt-2 text-xs text-[var(--chat-muted)]">
              ComfyUI checkpoint selected — Klein FLUX path bypassed. Step/CFG sliders honored as-is.
            </p>
          );
        })()}
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className={`block ${sliderConfig.cfg.disabled ? "opacity-50" : ""}`}>
          <span className="text-xs text-[var(--chat-muted)]">
            CFG Scale
            {sliderConfig.cfg.note && (
              <span className="ml-1 text-[10px] italic" title={sliderConfig.cfg.note}>
                (ignored)
              </span>
            )}
          </span>
          <input
            type="range"
            min={sliderConfig.cfg.min}
            max={sliderConfig.cfg.max}
            step={sliderConfig.cfg.step}
            value={imageSettings.cfg}
            disabled={sliderConfig.cfg.disabled}
            onChange={(e) => setImageSettings({ cfg: parseFloat(e.target.value) })}
            className="w-full mt-1 accent-violet-500 disabled:cursor-not-allowed"
            title={sliderConfig.cfg.note}
          />
          <span className="text-xs text-[var(--chat-muted)]">
            {imageSettings.cfg}
            <span className="ml-2 text-[10px] opacity-60">
              [{sliderConfig.cfg.min}–{sliderConfig.cfg.max}]
            </span>
          </span>
        </label>
        <label className="block">
          <span className="text-xs text-[var(--chat-muted)]">Steps</span>
          <input
            type="range"
            min={sliderConfig.steps.min}
            max={sliderConfig.steps.max}
            step={sliderConfig.steps.step}
            value={imageSettings.steps}
            onChange={(e) => setImageSettings({ steps: parseInt(e.target.value) })}
            className="w-full mt-1 accent-violet-500"
          />
          <span className="text-xs text-[var(--chat-muted)]">
            {imageSettings.steps}
            <span className="ml-2 text-[10px] opacity-60">
              [{sliderConfig.steps.min}–{sliderConfig.steps.max}]
            </span>
          </span>
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
