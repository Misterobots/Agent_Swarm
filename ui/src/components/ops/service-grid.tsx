"use client";

import { cn } from "@/lib/utils/cn";
import type { ClusterNode, ControlPlaneService } from "@/types/ops";

interface ServiceGridProps {
  title: string;
  services?: ControlPlaneService[];
  nodes?: ClusterNode[];
}

export function ServiceGrid({ title, services, nodes }: ServiceGridProps) {
  return (
    <div className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--chat-border)]">
        <h3 className="text-sm font-medium text-[var(--chat-text)]">{title}</h3>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-[var(--chat-muted)] border-b border-[var(--chat-border)]">
            <th className="text-left px-4 py-2 font-medium">Service</th>
            <th className="text-left px-4 py-2 font-medium">Status</th>
            <th className="text-right px-4 py-2 font-medium">Port</th>
          </tr>
        </thead>
        <tbody>
          {services?.map((svc) => (
            <tr key={svc.name} className="border-b border-[var(--chat-border)] last:border-0">
              <td className="px-4 py-2 text-[var(--chat-text)]">{svc.name}</td>
              <td className="px-4 py-2">
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "w-2 h-2 rounded-full",
                      svc.healthy ? "bg-emerald-400" : "bg-red-400"
                    )}
                  />
                  <span className={cn(
                    "text-xs",
                    svc.healthy ? "text-emerald-400" : "text-red-400"
                  )}>
                    {svc.healthy ? "Healthy" : "Down"}
                  </span>
                </span>
              </td>
              <td className="px-4 py-2 text-right text-[var(--chat-muted)]">{svc.port}</td>
            </tr>
          ))}
          {nodes?.map((node) => (
            <tr key={node.ip} className="border-b border-[var(--chat-border)] last:border-0">
              <td className="px-4 py-2 text-[var(--chat-text)]">{node.name}</td>
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
                    {node.healthy ? `${node.running_count} containers` : "Offline"}
                  </span>
                </span>
              </td>
              <td className="px-4 py-2 text-right text-[var(--chat-muted)]">{node.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
