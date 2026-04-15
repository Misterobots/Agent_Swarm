"use client";

import { useModels } from "@/lib/hooks/use-models";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { ChevronDown, Github } from "lucide-react";
import type { Model } from "@/types/chat";

function groupModels(models: Model[]) {
  const local: Model[] = [];
  const github: Model[] = [];
  for (const m of models) {
    if (m.id.startsWith("github/")) github.push(m);
    else local.push(m);
  }
  return { local, github };
}

export function ModelSelector() {
  const { models, loading } = useModels();
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);

  const { local, github } = groupModels(models);

  return (
    <div className="relative inline-flex items-center">
      <select
        value={model}
        onChange={(e) => setModel(e.target.value)}
        disabled={loading}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-sm border border-[var(--chat-border)] rounded-lg pl-3 pr-8 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer"
      >
        {local.length > 0 || github.length > 0 ? (
          <>
            {local.length > 0 && (
              <optgroup label="Local">
                {local.map((m) => (
                  <option key={m.id} value={m.id}>{m.id}</option>
                ))}
              </optgroup>
            )}
            {github.length > 0 && (
              <optgroup label="GitHub Models">
                {github.map((m) => (
                  <option key={m.id} value={m.id}>{m.id.replace("github/", "")}</option>
                ))}
              </optgroup>
            )}
            {github.length === 0 && (
              <option value="__connect_github__" disabled>
                ＋ Connect GitHub for cloud models
              </option>
            )}
          </>
        ) : (
          <option value="Home-AI-Swarm">Home-AI-Swarm</option>
        )}
      </select>
      {model.startsWith("github/") ? (
        <Github size={13} className="absolute right-2 text-[var(--chat-muted)] pointer-events-none" />
      ) : (
        <ChevronDown size={14} className="absolute right-2 text-[var(--chat-muted)] pointer-events-none" />
      )}
    </div>
  );
}
