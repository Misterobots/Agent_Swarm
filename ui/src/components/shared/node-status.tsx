"use client";

import { useEffect, useState } from "react";
import { fetchNodeHealth } from "@/lib/api/chat";
import type { NodeHealth } from "@/types/chat";
import { cn } from "@/lib/utils/cn";
import { Activity } from "lucide-react";

export function NodeStatus() {
  const [nodes, setNodes] = useState<NodeHealth[]>([]);

  useEffect(() => {
    const poll = () => fetchNodeHealth().then(setNodes).catch(() => {});
    poll();
    const interval = setInterval(poll, 30000);
    return () => clearInterval(interval);
  }, []);

  if (nodes.length === 0) return null;

  const healthyCount = nodes.filter((n) => n.healthy).length;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--chat-muted)]">
      <Activity size={12} />
      <span>
        {healthyCount}/{nodes.length} nodes
      </span>
      {nodes.map((n) => (
        <span
          key={n.host}
          className={cn(
            "w-2 h-2 rounded-full",
            n.healthy ? "bg-emerald-400" : "bg-red-400"
          )}
          title={`${n.name}: ${n.healthy ? "healthy" : "down"} (${n.available_models.length} models)`}
        />
      ))}
    </div>
  );
}
