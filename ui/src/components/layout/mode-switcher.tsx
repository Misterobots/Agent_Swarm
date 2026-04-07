"use client";

import { useSettingsStore } from "@/lib/stores/settings-store";
import { MessageSquare, Code2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useRouter } from "next/navigation";

export function ModeSwitcher() {
  const mode = useSettingsStore((s) => s.mode);
  const setMode = useSettingsStore((s) => s.setMode);
  const router = useRouter();

  const switchTo = (target: "standard" | "developer") => {
    setMode(target);
    router.push(target === "standard" ? "/chat" : "/dev");
  };

  return (
    <div className="flex bg-[var(--chat-panel)] rounded-lg p-0.5 gap-0.5">
      <button
        onClick={() => switchTo("standard")}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
          mode === "standard"
            ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] text-[var(--chat-accent)]"
            : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
        )}
      >
        <MessageSquare size={13} />
        Standard
      </button>
      <button
        onClick={() => switchTo("developer")}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
          mode === "developer"
            ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] text-[var(--chat-accent)]"
            : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
        )}
      >
        <Code2 size={13} />
        Developer
      </button>
    </div>
  );
}
