"use client";

import { cn } from "@/lib/utils/cn";
import type { ServiceStatus } from "@/types/ops";
import type { NodeHealth } from "@/types/chat";

interface ServiceGridProps {
  title: string;
  services?: ServiceStatus[];
  nodes?: NodeHealth[];
}

export function ServiceGrid({ title, services, nodes }: ServiceGridProps) {
  return (
    <div className="bg-[#1a1a2e] border border-zinc-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800">
        <h3 className="text-sm font-medium text-zinc-300">{title}</h3>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-zinc-500 border-b border-zinc-800/50">
            <th className="text-left px-4 py-2 font-medium">Service</th>
            <th className="text-left px-4 py-2 font-medium">Status</th>
            <th className="text-right px-4 py-2 font-medium">Port</th>
          </tr>
        </thead>
        <tbody>
          {services?.map((svc) => (
            <tr key={svc.name} className="border-b border-zinc-800/30 last:border-0">
              <td className="px-4 py-2 text-zinc-300">{svc.name}</td>
              <td className="px-4 py-2">
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "w-2 h-2 rounded-full",
                      svc.status === "healthy" ? "bg-emerald-400" : "bg-red-400"
                    )}
                  />
                  <span className={cn(
                    "text-xs",
                    svc.status === "healthy" ? "text-emerald-400" : "text-red-400"
                  )}>
                    {svc.status === "healthy" ? "Healthy" : "Down"}
                  </span>
                </span>
              </td>
              <td className="px-4 py-2 text-right text-zinc-500">{svc.port}</td>
            </tr>
          ))}
          {nodes?.map((node) => (
            <tr key={node.host} className="border-b border-zinc-800/30 last:border-0">
              <td className="px-4 py-2 text-zinc-300">{node.name}</td>
              <td className="px-4 py-2">
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "w-2 h-2 rounded-full",
                      node.healthy ? "bg-emerald-400" : "bg-red-400"
                    )}
                  />
                  <span className={cn(
                    "text-xs",
                    node.healthy ? "text-emerald-400" : "text-red-400"
                  )}>
                    {node.healthy ? `${node.loaded_models.length} models loaded` : "Offline"}
                  </span>
                </span>
              </td>
              <td className="px-4 py-2 text-right text-zinc-500">11434</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
