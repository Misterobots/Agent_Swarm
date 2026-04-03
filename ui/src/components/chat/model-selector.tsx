"use client";

import { useModels } from "@/lib/hooks/use-models";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useAccess } from "@/lib/hooks/use-access";
import { canSelectModel } from "@/lib/utils/model-access";
import { ChevronDown } from "lucide-react";

export function ModelSelector() {
  const { models, loading } = useModels();
  const { isAdmin, loading: accessLoading } = useAccess();
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);
  const visibleModels = models.filter((m) => canSelectModel(m.id, isAdmin));

  const selectedModel = canSelectModel(model, isAdmin)
    ? model
    : visibleModels[0]?.id || "swarm-standard";

  const handleChange = (nextModel: string) => {
    if (!canSelectModel(nextModel, isAdmin)) return;
    setModel(nextModel);
  };

  return (
    <div className="relative inline-flex items-center">
      <select
        value={selectedModel}
        onChange={(e) => handleChange(e.target.value)}
        disabled={loading || accessLoading}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-sm border border-[var(--chat-border)] rounded-lg pl-3 pr-8 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer"
      >
        {visibleModels.length > 0 ? (
          visibleModels.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id}
            </option>
          ))
        ) : (
          <option value="swarm-standard">swarm-standard</option>
        )}
      </select>
      <ChevronDown size={14} className="absolute right-2 text-[var(--chat-muted)] pointer-events-none" />
    </div>
  );
}
