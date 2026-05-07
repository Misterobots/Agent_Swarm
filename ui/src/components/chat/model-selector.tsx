"use client";

import { useSettingsStore } from "@/lib/stores/settings-store";
import { ChevronDown } from "lucide-react";
import { useRef, useState, useEffect, useCallback } from "react";
import { fetchModels } from "@/lib/api/chat";
import type { Model } from "@/types/chat";

const DEFAULT_MODEL_ID = "Home-AI-Swarm";

/** Always-available local fallback so the selector never appears empty. */
const LOCAL_FALLBACK: Model[] = [
  { id: "Home-AI-Swarm",  object: "model", created: 0, owned_by: "MarsRL", label: "Memex" },
  { id: "swarm-standard", object: "model", created: 0, owned_by: "MarsRL", label: "Swarm Standard" },
];

/** Human-readable group header for each owned_by value. */
const OWNER_LABEL: Record<string, string> = {
  MarsRL:    "Local",
  github:    "GitHub Models",
  anthropic: "Anthropic",
  google:    "Google",
};

type ModelGroup = { owner: string; groupLabel: string; models: Model[] };

function groupModels(models: Model[]): ModelGroup[] {
  const map = new Map<string, Model[]>();
  for (const m of models) {
    const key = m.owned_by || "MarsRL";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(m);
  }
  // Local models first, then external providers alphabetically
  const orderedKeys = Array.from(map.keys()).sort((a, b) => {
    if (a === "MarsRL") return -1;
    if (b === "MarsRL") return 1;
    return a.localeCompare(b);
  });
  return orderedKeys.map((owner) => ({
    owner,
    groupLabel: OWNER_LABEL[owner] ?? owner,
    models: map.get(owner)!,
  }));
}

export function ModelSelector() {
  const model    = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);
  const [allModels, setAllModels] = useState<Model[]>(LOCAL_FALLBACK);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadModels = useCallback(async () => {
    try {
      const fetched = await fetchModels();
      if (fetched.length > 0) {
        setAllModels(fetched);
        // If the stored model is no longer in the list, reset to default
        const validIds = new Set(fetched.map((m) => m.id));
        if (!validIds.has(model)) setModel(DEFAULT_MODEL_ID);
      }
    } catch {
      // Network error — keep existing list (local fallback stays visible)
    }
  }, [model, setModel]);

  // Fetch on mount
  useEffect(() => {
    loadModels();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch when user returns to this tab (e.g. after connecting an account
  // in settings or in another tab) — keeps the list fresh without polling
  useEffect(() => {
    const onFocus = () => loadModels();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loadModels]);

  const groups = groupModels(allModels);
  const useOptGroups = groups.length > 1;
  const displayLabel = allModels.find((m) => m.id === model)?.label ?? model;

  return (
    <div className="group relative inline-flex items-center" ref={containerRef}>
      <select
        value={model}
        onChange={(e) => setModel(e.target.value)}
        title={displayLabel}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-sm border border-[var(--chat-border)] rounded-lg pl-3 pr-10 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer max-w-[140px] md:max-w-none"
      >
        {groups.map(({ owner, groupLabel, models }) =>
          useOptGroups ? (
            <optgroup key={owner} label={groupLabel}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label ?? m.id}
                </option>
              ))}
            </optgroup>
          ) : (
            models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label ?? m.id}
              </option>
            ))
          )
        )}
      </select>
      <ChevronDown size={14} className="absolute right-3 text-[var(--chat-muted)] pointer-events-none" />
    </div>
  );
}

