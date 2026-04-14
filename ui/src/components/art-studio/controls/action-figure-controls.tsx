"use client";

import { useArtStore } from "@/lib/stores/art-store";

const WORKFLOWS = [
  { label: "TripoSG (Fast)", value: "workflow_triposg.json" },
  { label: "Hunyuan 3D (Textured)", value: "workflow_hunyuan_paint.json" },
];

export function ActionFigureControls() {
  const { actionFigureSettings, setActionFigureSettings } = useArtStore();

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider">
        Action Figure
      </h3>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">Base Mesh Pipeline</span>
        <select
          value={actionFigureSettings.workflow}
          onChange={(e) => setActionFigureSettings({ workflow: e.target.value })}
          className="mt-1 w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500"
        >
          {WORKFLOWS.map((w) => (
            <option key={w.value} value={w.value}>{w.label}</option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">
          Figure Height: {actionFigureSettings.targetHeight}mm
        </span>
        <input
          type="range"
          min={50} max={300} step={10}
          value={actionFigureSettings.targetHeight}
          onChange={(e) => setActionFigureSettings({ targetHeight: parseInt(e.target.value) })}
          className="w-full mt-1 accent-violet-500"
        />
        <div className="flex justify-between text-[10px] text-[var(--chat-muted)]">
          <span>50mm</span><span>300mm</span>
        </div>
      </label>

      <label className="block">
        <span className="text-xs text-[var(--chat-muted)]">
          Joint Clearance: {actionFigureSettings.clearance}mm
        </span>
        <input
          type="range"
          min={0.1} max={0.5} step={0.05}
          value={actionFigureSettings.clearance}
          onChange={(e) => setActionFigureSettings({ clearance: parseFloat(e.target.value) })}
          className="w-full mt-1 accent-violet-500"
        />
        <div className="flex justify-between text-[10px] text-[var(--chat-muted)]">
          <span>0.1 (resin)</span><span>0.5 (FDM)</span>
        </div>
      </label>

      <div className="rounded-lg bg-[var(--chat-panel)] border border-[var(--chat-border)] p-3">
        <p className="text-xs text-[var(--chat-muted)] font-medium mb-2">Joint Locations (12)</p>
        <div className="flex flex-wrap gap-1.5">
          {["Neck", "L Shoulder", "R Shoulder", "L Elbow", "R Elbow", "L Wrist", "R Wrist", "Waist", "L Hip", "R Hip", "L Knee", "R Knee"].map((j) => (
            <span
              key={j}
              className="px-2 py-0.5 rounded-full bg-violet-900/30 text-violet-300 text-[10px] font-medium"
            >
              {j}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
