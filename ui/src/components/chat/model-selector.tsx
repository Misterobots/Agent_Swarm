"use client";

import { useModels } from "@/lib/hooks/use-models";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { ChevronDown } from "lucide-react";

export function ModelSelector() {
  const { models, loading } = useModels();
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);

  return (
    <div className="relative inline-flex items-center">
      <select
        value={model}
        onChange={(e) => setModel(e.target.value)}
        disabled={loading}
        className="appearance-none bg-[#1a1a2e] text-zinc-300 text-sm border border-zinc-700 rounded-lg pl-3 pr-8 py-1.5 focus:border-cyan-500 focus:outline-none cursor-pointer"
      >
        {models.length > 0 ? (
          models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id}
            </option>
          ))
        ) : (
          <option value="swarm-standard">swarm-standard</option>
        )}
      </select>
      <ChevronDown size={14} className="absolute right-2 text-zinc-500 pointer-events-none" />
    </div>
  );
}
