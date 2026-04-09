"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ClusterNode, ControlPlaneService } from "@/types/ops";

interface AlertBannerProps {
  services: ControlPlaneService[];
  nodes: ClusterNode[];
}

export function AlertBanner({ services, nodes }: AlertBannerProps) {
  const downServices = services.filter((s) => !s.healthy);
  const downNodes = nodes.filter((n) => !n.healthy);

  if (downServices.length === 0 && downNodes.length === 0) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 bg-emerald-900/20 border border-emerald-800/30 rounded-lg">
        <CheckCircle2 size={16} className="text-emerald-400" />
        <span className="text-sm text-emerald-300">All systems operational</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {downServices.map((svc) => (
        <div
          key={svc.name}
          className="flex items-center gap-2 px-4 py-3 bg-red-900/20 border border-red-800/30 rounded-lg"
        >
          <AlertTriangle size={16} className="text-red-400" />
          <span className="text-sm text-red-300">
            {svc.name} is down (port {svc.port})
          </span>
        </div>
      ))}
      {downNodes.map((node) => (
        <div
          key={node.ip}
          className="flex items-center gap-2 px-4 py-3 bg-red-900/20 border border-red-800/30 rounded-lg"
        >
          <AlertTriangle size={16} className="text-red-400" />
          <span className="text-sm text-red-300">
            Inference node &quot;{node.name}&quot; is offline ({node.ip})
          </span>
        </div>
      ))}
    </div>
  );
}
