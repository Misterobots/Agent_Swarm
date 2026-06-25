"use client";

import { useEffect, useState } from "react";
import { useDesktop } from "@/lib/hooks/use-desktop";

interface UpdateStatus {
  state: "checking" | "available" | "downloading" | "ready" | "current" | "error";
  version?: string;
  percent?: number;
  message?: string;
}

export function UpdateBanner() {
  const { inDesktop, bridge } = useDesktop();
  const [status, setStatus] = useState<UpdateStatus | null>(null);

  useEffect(() => {
    if (!inDesktop || !bridge) return;
    const off = bridge.updater.onStatus(setStatus);
    return off;
  }, [inDesktop, bridge]);

  if (!status || status.state === "checking" || status.state === "current") return null;

  if (status.state === "downloading") {
    return (
      <div className="flex items-center gap-3 px-4 py-1.5 bg-[var(--chat-surface)] border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
        <div className="w-24 h-1 rounded-full bg-[var(--chat-border)] overflow-hidden">
          <div
            className="h-full bg-[var(--chat-accent)] transition-all duration-300"
            style={{ width: `${status.percent ?? 0}%` }}
          />
        </div>
        <span>Downloading update {status.version}… {status.percent ?? 0}%</span>
      </div>
    );
  }

  if (status.state === "ready") {
    return (
      <div className="flex items-center justify-between px-4 py-1.5 bg-[var(--chat-accent)]/10 border-b border-[var(--chat-accent)]/30 text-xs">
        <span className="text-[var(--chat-text)]">
          Memex Desktop <strong>{status.version}</strong> is ready to install.
        </span>
        <button
          onClick={() => bridge?.updater.install()}
          className="px-3 py-1 rounded-md bg-[var(--chat-accent)] text-canvas font-medium hover:opacity-90 transition-opacity"
        >
          Restart &amp; update
        </button>
      </div>
    );
  }

  if (status.state === "error") {
    return (
      <div className="px-4 py-1.5 bg-red-950/20 border-b border-red-700/30 text-xs text-red-400">
        Update check failed: {status.message}
      </div>
    );
  }

  return null;
}
