"use client";

import { useState } from "react";
import { BookOpen, Lock } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useGroundingPermissions } from "@/lib/hooks/use-grounding-permissions";

export function DocGroundingToggle() {
  const groundingDocs = useSettingsStore((s) => s.groundingDocs);
  const setGroundingDocs = useSettingsStore((s) => s.setGroundingDocs);
  const { status, loading, request } = useGroundingPermissions();
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);

  const permitted = !loading && status.docs_grounding;

  const handleClick = async () => {
    if (permitted) {
      setGroundingDocs(!groundingDocs);
      return;
    }
    if (requesting || requested) return;
    setRequesting(true);
    try {
      await request("docs_grounding", "Requesting document grounding access for knowledge-base retrieval.");
      setRequested(true);
    } catch {
      // request submission failed — silently swallow
    } finally {
      setRequesting(false);
    }
  };

  const label = requesting
    ? "Requesting…"
    : requested
    ? "Pending Approval"
    : permitted
    ? "Docs"
    : "Docs (Locked)";

  const title = permitted
    ? "Toggle document grounding — inject relevant knowledge-base chunks before responding"
    : requested
    ? "Document grounding approval is pending admin review"
    : "Document grounding requires a governance approval. Click to submit a request.";

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={requesting}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        !permitted
          ? "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] opacity-60 cursor-pointer"
          : groundingDocs
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title={title}
    >
      {permitted ? <BookOpen size={14} /> : <Lock size={14} />}
      {label}
    </button>
  );
}
