"use client";

import { useSettingsStore } from "@/lib/stores/settings-store";
import { ChevronDown } from "lucide-react";
import { useRef, useEffect } from "react";

const MEMEX_MODEL_ID = "Home-AI-Swarm";

export function ModelSelector() {
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);
  const containerRef = useRef<HTMLDivElement>(null);

  // Ensure the stored model is always the Memex swarm ID
  useEffect(() => {
    if (model !== MEMEX_MODEL_ID) setModel(MEMEX_MODEL_ID);
  }, [model, setModel]);

  return (
    <div className="group relative inline-flex items-center" ref={containerRef}>
      <select
        value={MEMEX_MODEL_ID}
        onChange={() => {/* single option — no-op */}}
        className="appearance-none bg-[var(--chat-panel)] text-[var(--chat-text)] text-sm border border-[var(--chat-border)] rounded-lg pl-3 pr-10 py-1.5 focus:border-[var(--chat-accent)] focus:outline-none cursor-pointer max-w-[140px] md:max-w-none"
      >
        <option value={MEMEX_MODEL_ID}>Memex</option>
      </select>
      <ChevronDown size={14} className="absolute right-3 text-[var(--chat-muted)] pointer-events-none" />
    </div>
  );
}


