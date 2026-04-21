"use client";

import { useState } from "react";
import { FolderOpen, Lock } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useGroundingPermissions } from "@/lib/hooks/use-grounding-permissions";

export function FileGroundingToggle() {
  const groundingFile = useSettingsStore((s) => s.groundingFile);
  const setGroundingFile = useSettingsStore((s) => s.setGroundingFile);
  const { status, loading, request } = useGroundingPermissions();
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);

  const permitted = !loading && status.file_grounding;

  const handleClick = async () => {
    if (permitted) {
      setGroundingFile(!groundingFile);
      return;
    }
    if (requesting || requested) return;
    setRequesting(true);
    try {
      await request("file_grounding", "Requesting workspace filespace grounding access for local file retrieval.");
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
    ? "Files"
    : "Files (Locked)";

  const title = permitted
    ? "Toggle file grounding — inject relevant workspace file content before responding"
    : requested
    ? "File grounding approval is pending admin review"
    : "File grounding requires a governance approval. Click to submit a request.";

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={requesting}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        !permitted
          ? "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] opacity-60 cursor-pointer"
          : groundingFile
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title={title}
    >
      {permitted ? <FolderOpen size={14} /> : <Lock size={14} />}
      {label}
    </button>
  );
}
