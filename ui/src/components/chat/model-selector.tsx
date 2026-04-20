"use client";

import { useModels } from "@/lib/hooks/use-models";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { ChevronDown, Github } from "lucide-react";
import type { Model } from "@/types/chat";
import { useRef } from "react";

function groupModels(models: Model[]) {
  const local: Model[] = [];
  const github: Model[] = [];
  const connected: Model[] = [];
  for (const m of models) {
    if (m.id.startsWith("github/")) github.push(m);
    else if (["anthropic", "google"].includes(m.owned_by)) connected.push(m);
    else local.push(m);
  }
  return { local, github, connected };
}

function displayName(m: Model): string {
  return m.label || m.id;
}

export function ModelSelector() {
  const { models, loading } = useModels();
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);
  const containerRef = useRef<HTMLDivElement>(null);

  const { local, github, connected } = groupModels(models);

  // Find description for current model
  const currentModel = models.find((m) => m.id === model);

  return (
    <div className="group relative inline-flex items-center" ref={containerRef}>
      <select
        value={model}
        onChange={(e) => setModel(e.target.value)}
        disabled={loading}
        title={currentModel?.description || ""}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-sm border border-[var(--chat-border)] rounded-lg pl-3 pr-8 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer max-w-[140px] md:max-w-none truncate"
      >
        {local.length > 0 || github.length > 0 || connected.length > 0 ? (
          <>
            {local.length > 0 && (
              <optgroup label="Local">
                {local.map((m) => (
                  <option key={m.id} value={m.id}>{displayName(m)}</option>
                ))}
              </optgroup>
            )}
            {connected.length > 0 && (
              <optgroup label="Connected">
                {connected.map((m) => (
                  <option key={m.id} value={m.id}>{displayName(m)}</option>
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
            {github.length === 0 && connected.length === 0 && (
              <option value="__connect_provider__" disabled>
                ＋ Connect a provider for cloud models
              </option>
            )}
          </>
        ) : (
          <option value="hive-mind">Hive Mind</option>
        )}
      </select>
      {model.startsWith("github/") ? (
        <Github size={13} className="absolute right-2 text-[var(--chat-muted)] pointer-events-none" />
      ) : (
        <ChevronDown size={14} className="absolute right-2 text-[var(--chat-muted)] pointer-events-none" />
      )}
      {/* Tooltip shown below selector on hover */}
      {currentModel?.description && (
        <div
          className="absolute left-0 top-full mt-1 z-50 hidden group-hover:block"
          style={{ pointerEvents: "none" }}
        >
          <div className="bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-md px-3 py-2 text-xs text-[var(--chat-muted)] max-w-[280px] shadow-lg">
            {currentModel.description}
          </div>
        </div>
      )}
    </div>
  );
}
