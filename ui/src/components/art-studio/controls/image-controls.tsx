"use client";

import { useArtStore } from "@/lib/stores/art-store";

const SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"];
const SCHEDULERS = ["normal", "karras", "simple", "sgm_uniform"];
const ASPECTS = [
  { label: "1:1 Square", w: 1024, h: 1024 },
  { label: "16:9 Cinematic", w: 1344, h: 768 },
  { label: "9:16 Portrait", w: 768, h: 1344 },
];

export function ImageControls({ models }: { models: string[] }) {
  const { imageSettings, setImageSettings } = useArtStore();

  const currentAspect = ASPECTS.find(
    (a) => a.w === imageSettings.width && a.h === imageSettings.height
  ) || ASPECTS[0];

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
        Image Settings
      </h3>

      <label className="block">
        <span className="text-xs text-zinc-500">Model</span>
        <select
          value={imageSettings.model}
          onChange={(e) => setImageSettings({ model: e.target.value })}
          className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-violet-500"
        >
          <option value="auto">Auto-detect</option>
          {models.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="text-xs text-zinc-500">CFG Scale</span>
          <input
            type="range"
            min={1} max={20} step={0.5}
            value={imageSettings.cfg}
            onChange={(e) => setImageSettings({ cfg: parseFloat(e.target.value) })}
            className="w-full mt-1 accent-violet-500"
          />
          <span className="text-xs text-zinc-600">{imageSettings.cfg}</span>
        </label>
        <label className="block">
          <span className="text-xs text-zinc-500">Steps</span>
          <input
            type="range"
            min={1} max={50} step={1}
            value={imageSettings.steps}
            onChange={(e) => setImageSettings({ steps: parseInt(e.target.value) })}
            className="w-full mt-1 accent-violet-500"
          />
          <span className="text-xs text-zinc-600">{imageSettings.steps}</span>
        </label>
      </div>

      <label className="block">
        <span className="text-xs text-zinc-500">Aspect Ratio</span>
        <select
          value={`${currentAspect.w}x${currentAspect.h}`}
          onChange={(e) => {
            const [w, h] = e.target.value.split("x").map(Number);
            setImageSettings({ width: w, height: h });
          }}
          className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-violet-500"
        >
          {ASPECTS.map((a) => (
            <option key={`${a.w}x${a.h}`} value={`${a.w}x${a.h}`}>
              {a.label} ({a.w}x{a.h})
            </option>
          ))}
        </select>
      </label>

      <details className="group">
        <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300 transition-colors">
          Advanced Settings
        </summary>
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-zinc-500">Sampler</span>
              <select
                value={imageSettings.sampler}
                onChange={(e) => setImageSettings({ sampler: e.target.value })}
                className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-violet-500"
              >
                {SAMPLERS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-zinc-500">Scheduler</span>
              <select
                value={imageSettings.scheduler}
                onChange={(e) => setImageSettings({ scheduler: e.target.value })}
                className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-violet-500"
              >
                {SCHEDULERS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <label className="block">
            <span className="text-xs text-zinc-500">Seed (-1 = random)</span>
            <input
              type="number"
              value={imageSettings.seed}
              onChange={(e) => setImageSettings({ seed: parseInt(e.target.value) || -1 })}
              className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-violet-500"
            />
          </label>
        </div>
      </details>
    </div>
  );
}
