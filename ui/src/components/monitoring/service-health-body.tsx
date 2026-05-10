"use client";

import {
  CheckCircle2,
  Loader2,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { WorkspaceSection } from "@/components/workspace/workspace-shell";
import { Button, Card, IconButton } from "@/components/ui";
import { fetchServiceChecks, restartService } from "@/lib/api/ops";
import { useCallback, useEffect, useState } from "react";
import type { ServiceCheck } from "@/types/ops";
import { cn } from "@/lib/utils/cn";

const REFRESH_MS = 30_000;

function StatusBadge({ healthy, latency }: { healthy: boolean; latency: number | null }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-[11px] font-medium",
        healthy ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400",
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", healthy ? "bg-emerald-400" : "bg-red-400 animate-pulse")} />
      <span>{healthy ? "Healthy" : "Down"}</span>
      {healthy && latency != null && (
        <span className="text-[var(--chat-muted)] tabular-nums">· {latency}ms</span>
      )}
    </span>
  );
}

function ServiceCard({
  svc,
  onRestart,
  restarting,
}: {
  svc: ServiceCheck;
  onRestart: (id: string) => void;
  restarting: boolean;
}) {
  return (
    <Card
      padding="md"
      style={
        !svc.healthy
          ? { background: "color-mix(in srgb, #f87171 8%, var(--chat-surface))" }
          : undefined
      }
      className={cn(!svc.healthy && "!border-red-900/60")}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-[var(--chat-text)]">{svc.name}</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--chat-subtle)] truncate">
            {svc.ip}:{svc.port} · {svc.container}
          </p>
        </div>
        <IconButton
          label={`Restart ${svc.name}`}
          icon={restarting ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
          onClick={() => onRestart(svc.id)}
          disabled={restarting}
          variant="ghost"
          size="sm"
        />
      </div>
      <div className="mt-2.5">
        <StatusBadge healthy={svc.healthy} latency={svc.latency_ms} />
      </div>
      {svc.detail && (
        <p className="mt-2 text-[11px] text-[var(--chat-muted)] tabular-nums">{svc.detail}</p>
      )}
    </Card>
  );
}

export function ServiceHealthBody() {
  const [services, setServices] = useState<ServiceCheck[]>([]);
  const [summary, setSummary] = useState({ total: 0, healthy: 0, unhealthy: 0 });
  const [loading, setLoading] = useState(true);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  const [restartingIds, setRestartingIds] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<{ id: string; msg: string; ok: boolean }[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchServiceChecks();
      setServices(data.services);
      setSummary(data.summary);
      setRefreshedAt(new Date());
    } catch {
      // keep previous state on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleRestart = useCallback(
    async (serviceId: string) => {
      setRestartingIds((prev) => new Set(prev).add(serviceId));
      const result = await restartService(serviceId);
      setRestartingIds((prev) => {
        const next = new Set(prev);
        next.delete(serviceId);
        return next;
      });

      const svc = services.find((s) => s.id === serviceId);
      const name = svc?.name ?? serviceId;
      const ok = result.status === "restarted";
      const msg = ok
        ? `${name} restarted successfully`
        : `${name} restart failed: ${result.detail}`;
      const toastId = `${serviceId}-${Date.now()}`;
      setToasts((prev) => [...prev, { id: toastId, msg, ok }]);
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== toastId)), 5000);

      if (ok) setTimeout(refresh, 3000);
    },
    [services, refresh],
  );

  const byNode = services.reduce<Record<string, ServiceCheck[]>>((acc, svc) => {
    (acc[svc.node] ??= []).push(svc);
    return acc;
  }, {});

  const nodeOrder = ["Turing", "Control Node", "Lovelace"];
  const sortedNodes = nodeOrder.filter((n) => byNode[n]);

  return (
    <>
      <Card padding="md" className="mb-6">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--chat-subtle)]">
              Services
            </span>
            {summary.unhealthy === 0 ? (
              <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-emerald-400">
                <CheckCircle2 size={14} />
                All {summary.total} healthy
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-red-400">
                <XCircle size={14} />
                {summary.unhealthy} unhealthy <span className="text-[var(--chat-muted)] tabular-nums">/ {summary.total}</span>
              </span>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={refresh}
            disabled={loading}
            iconLeft={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}
          >
            {refreshedAt ? `Updated ${refreshedAt.toLocaleTimeString()}` : "Loading…"}
          </Button>
        </div>
      </Card>

      {sortedNodes.map((node) => (
        <WorkspaceSection key={node} title={node} description={`${byNode[node].length} services`}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {byNode[node].map((svc) => (
              <ServiceCard
                key={svc.id}
                svc={svc}
                onRestart={handleRestart}
                restarting={restartingIds.has(svc.id)}
              />
            ))}
          </div>
        </WorkspaceSection>
      ))}

      {!loading && services.length === 0 && (
        <Card padding="lg" className="text-center">
          <p className="text-sm text-[var(--chat-muted)]">
            Unable to reach backend. Verify the API server is running on the execution node.
          </p>
        </Card>
      )}

      {/* Toast stack */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "rounded-md px-4 py-2.5 text-[13px] font-medium animate-in slide-in-from-right-3",
            )}
            style={{
              background: t.ok
                ? "color-mix(in srgb, #34d399 8%, var(--chat-surface))"
                : "color-mix(in srgb, #f87171 8%, var(--chat-surface))",
              border: t.ok
                ? "1px solid color-mix(in srgb, #34d399 35%, var(--chat-border))"
                : "1px solid color-mix(in srgb, #f87171 35%, var(--chat-border))",
              color: t.ok ? "#34d399" : "#f87171",
              boxShadow: "var(--elev-3)",
            }}
          >
            {t.msg}
          </div>
        ))}
      </div>
    </>
  );
}
