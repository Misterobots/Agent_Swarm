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
    <div className="flex bg-zinc-900 rounded-lg p-0.5 gap-0.5">
      <button
        onClick={() => switchTo("standard")}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
          mode === "standard"
            ? "bg-cyan-600/20 text-cyan-400"
            : "text-zinc-500 hover:text-zinc-300"
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
            ? "bg-cyan-600/20 text-cyan-400"
            : "text-zinc-500 hover:text-zinc-300"
        )}
      >
        <Code2 size={13} />
        Developer
      </button>
    </div>
  );
}
