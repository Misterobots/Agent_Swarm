"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";

// Pioneer role → initials for the avatar badge
const ROLE_INITIALS: Record<string, string> = {
  researcher: "SH",
  architect: "BA",
  coder: "KN",
  devops: "CE",
  analyst: "CO",
  verifier: "HO",
};

interface AgentIdCardProps {
  worker: SwarmWorker;
  onDone?: () => void;
}

export function AgentIdCard({ worker, onDone }: AgentIdCardProps) {
  const [stage, setStage] = useState<"drop" | "straight" | "exit">("drop");
  const initials = ROLE_INITIALS[worker.role?.toLowerCase() ?? ""] ?? worker.pioneer_name?.slice(0, 2).toUpperCase() ?? "??";

  // drop → straight after 600ms, then call onDone after 2.4s hold
  useEffect(() => {
    const t1 = setTimeout(() => setStage("straight"), 600);
    const t2 = setTimeout(() => setStage("exit"), 3200);
    const t3 = setTimeout(() => onDone?.(), 3800);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [onDone]);

  return (
    <div className="flex items-center justify-center w-full h-full">
      <div
        className={cn(
          "relative w-56 rounded-2xl bg-white shadow-2xl overflow-hidden transition-all",
          "duration-500 ease-out",
          stage === "drop" && "opacity-0 -translate-y-8 rotate-[-10deg] scale-95",
          stage === "straight" && "opacity-100 translate-y-0 rotate-0 scale-100",
          stage === "exit" && "opacity-0 translate-y-4 scale-95 rotate-[3deg]",
        )}
      >
        {/* Lanyard bar */}
        <div className="h-7 bg-black flex items-center px-3">
          <span className="text-white font-bold text-xs tracking-widest">M</span>
          <div className="ml-auto w-4 h-4 rounded-full bg-white/20 border border-white/40" />
        </div>

        {/* Body */}
        <div className="px-5 pb-5 pt-4 flex flex-col items-center gap-3">
          {/* Avatar circle */}
          <div className="w-16 h-16 rounded-full bg-gray-900 flex items-center justify-center border-2 border-gray-200">
            <span className="text-white font-bold text-xl">{initials}</span>
          </div>

          {/* Name + role */}
          <div className="text-center">
            <p className="font-bold text-gray-900 text-sm leading-tight">{worker.pioneer_name}</p>
            <p className="text-gray-500 text-[11px] mt-0.5 capitalize">{worker.role}</p>
          </div>

          {/* Motto */}
          {worker.pioneer_motto && (
            <p className="text-gray-600 text-[10px] text-center leading-snug italic">
              &ldquo;{worker.pioneer_motto}&rdquo;
            </p>
          )}

          {/* Footer */}
          <div className="w-full flex items-center justify-between mt-1">
            <span className="font-black text-gray-900 text-xs tracking-widest">MEMEX</span>
            <div className="px-2 py-0.5 rounded-full bg-gray-900 text-white text-[9px] font-semibold">
              {worker.role.toUpperCase()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
