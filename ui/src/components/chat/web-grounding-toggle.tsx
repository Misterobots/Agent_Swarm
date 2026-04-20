"use client";

import { useState } from "react";
import { Globe, Lock } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useGroundingPermissions } from "@/lib/hooks/use-grounding-permissions";

export function WebGroundingToggle() {
  const groundingWeb = useSettingsStore((s) => s.groundingWeb);
  const setGroundingWeb = useSettingsStore((s) => s.setGroundingWeb);
  const { status, loading, request } = useGroundingPermissions();
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);

  const permitted = !loading && status.web_grounding;

  const handleClick = async () => {
    if (permitted) {
      setGroundingWeb(!groundingWeb);
      return;
    }
    if (requesting || requested) return;
    setRequesting(true);
    try {
      await request("web_grounding", "Requesting web grounding access for live search results.");
      setRequested(true);
    } catch {
      // request submission failed — silently swallow; admin can be contacted manually
    } finally {
      setRequesting(false);
    }
  };

  const label = requesting
    ? "Requesting…"
    : requested
    ? "Pending Approval"
    : permitted
    ? "Web"
    : "Web (Locked)";

  const title = permitted
    ? "Toggle internet grounding — inject live web search results before responding"
    : requested
    ? "Web grounding approval is pending admin review"
    : "Internet grounding requires a governance approval. Click to submit a request.";

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={requesting}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        !permitted
          ? "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] opacity-60 cursor-pointer"
          : groundingWeb
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title={title}
    >
      {permitted ? <Globe size={14} /> : <Lock size={14} />}
      {label}
    </button>
  );
}
