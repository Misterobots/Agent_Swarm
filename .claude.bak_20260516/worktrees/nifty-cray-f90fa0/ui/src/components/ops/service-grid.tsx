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
    <div className="surface overflow-hidden">
      <div
        className="px-4 py-3 border-b border-[var(--chat-border)]"
        style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
      >
        <h3 className="text-[13px] font-semibold tracking-tight text-[var(--chat-text)]">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-[var(--chat-subtle)]">
              <th className="text-left px-4 py-2 font-semibold">Service</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-right px-4 py-2 font-semibold">Port</th>
            </tr>
          </thead>
          <tbody>
            {services?.map((svc, i) => (
              <ServiceRow
                key={svc.name}
                name={svc.name}
                healthy={svc.healthy}
                healthLabel={svc.healthy ? "Healthy" : "Down"}
                trailing={String(svc.port)}
                isLast={i === (services.length - 1)}
              />
            ))}
            {nodes?.map((node, i) => (
              <ServiceRow
                key={node.ip}
                name={node.name}
                healthy={node.healthy}
                healthLabel={node.healthy ? `${node.running_count} containers` : "Offline"}
                trailing={node.role}
                isLast={i === (nodes.length - 1)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ServiceRow({
  name,
  healthy,
  healthLabel,
  trailing,
  isLast,
}: {
  name: string;
  healthy: boolean;
  healthLabel: string;
  trailing: string;
  isLast: boolean;
}) {
  return (
    <tr
      className={cn(
        "transition-colors hover:bg-[var(--hover-tint)]",
        !isLast && "border-b border-[var(--divider)]",
      )}
    >
      <td className="px-4 py-2.5 text-[13px] text-[var(--chat-text)]">{name}</td>
      <td className="px-4 py-2.5">
        <span className="flex items-center gap-2">
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full flex-shrink-0",
              healthy ? "bg-emerald-400" : "bg-red-400 animate-pulse",
            )}
          />
          <span
            className={cn(
              "text-[12px] font-medium",
              healthy ? "text-emerald-400" : "text-red-400",
            )}
          >
            {healthLabel}
          </span>
        </span>
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-[12px] tabular-nums text-[var(--chat-muted)]">
        {trailing}
      </td>
    </tr>
  );
}
