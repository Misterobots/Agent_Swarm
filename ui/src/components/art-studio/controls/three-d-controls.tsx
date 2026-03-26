"use client";

import { useArtStore } from "@/lib/stores/art-store";

const WORKFLOWS = [
  { label: "TripoSG (Fast, ~2 min)", value: "workflow_triposg.json" },
  { label: "Hunyuan 3D (Textured, ~8 min)", value: "workflow_hunyuan_paint.json" },
];

export function ThreeDControls() {
  const { threeDSettings, setThreeDSettings } = useArtStore();

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
        3D Generation
      </h3>

      <label className="block">
        <span className="text-xs text-zinc-500">Pipeline</span>
        <select
          value={threeDSettings.workflow}
          onChange={(e) => setThreeDSettings({ workflow: e.target.value })}
          className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-violet-500"
        >
          {WORKFLOWS.map((w) => (
            <option key={w.value} value={w.value}>{w.label}</option>
          ))}
        </select>
      </label>

      <p className="text-xs text-zinc-600">
        TripoSG produces untextured GLB meshes quickly. Hunyuan generates full-color textured meshes but takes longer.
      </p>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={threeDSettings.autoConcept}
          onChange={(e) => setThreeDSettings({ autoConcept: e.target.checked })}
          className="rounded border-zinc-700 bg-zinc-900 text-violet-500 focus:ring-violet-500"
        />
        <span className="text-xs text-zinc-400">Auto-generate concept art first</span>
      </label>

      <p className="text-xs text-zinc-600">
        When enabled, the system creates concept art from your prompt before converting to 3D.
      </p>
    </div>
  );
}
