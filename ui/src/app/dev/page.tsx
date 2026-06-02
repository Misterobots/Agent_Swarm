"use client";

import { DevWorkspace } from "@/components/dev/dev-workspace";
import { useDevStore } from "@/lib/stores/dev-store";
import { useAccess } from "@/lib/hooks/use-access";
import { useDevSessionSync } from "@/lib/hooks/use-dev-session-sync";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Bot } from "lucide-react";

export default function DevPage() {
  const { isAdmin, loading } = useAccess();
  const router = useRouter();

  // Cross-device dev session sync — must be called unconditionally (React rules)
  useDevSessionSync();

  useEffect(() => {
    if (!loading && !isAdmin) {
      router.replace("/chat");
    }
  }, [loading, isAdmin, router]);

  const {
    agentEnabled,
    setAgentEnabled,
  } = useDevStore();

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-[var(--chat-muted)] text-sm">
        Checking access…
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--chat-bg)] border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold text-[var(--chat-text)]">Developer Workspace</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Agent mode toggle */}
          <button
            onClick={() => setAgentEnabled(!agentEnabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border transition-colors ${
              agentEnabled
                ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
                : "bg-[var(--chat-input-bg)] text-[var(--chat-muted)] border-transparent hover:text-[var(--chat-text)]"
            }`}
            title="Toggle agent mode (file + terminal access)"
          >
            <Bot size={14} />
            Agent Mode
          </button>
        </div>
      </div>

      {/* Workspace */}
      <div className="flex-1 overflow-hidden">
        <DevWorkspace />
      </div>
    </div>
  );
}
