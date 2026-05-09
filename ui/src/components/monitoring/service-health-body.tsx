"use client";

import {
  CheckCircle2,
  Loader2,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { WorkspaceSection } from "@/components/workspace/workspace-shell";
import { fetchServiceChecks, restartService } from "@/lib/api/ops";
import { useCallback, useEffect, useState } from "react";
import type { ServiceCheck } from "@/types/ops";

const REFRESH_MS = 30_000;

function StatusDot({ healthy, latency }: { healthy: boolean; latency: number | null }) {
  return healthy ? (
    <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
      <CheckCircle2 size={14} />
      <span>Healthy</span>
      {latency != null && <span className="text-[var(--chat-muted)]">({latency}ms)</span>}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs text-red-400">
      <XCircle size={14} />
      <span>Down</span>
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
    <div
      className={`rounded-lg border p-4 ${
        svc.healthy
          ? "border-[var(--chat-border)] bg-[var(--chat-panel)]"
          : "border-red-900/60 bg-red-950/30"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-[var(--chat-text)]">{svc.name}</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--chat-muted)]">
            {svc.ip}:{svc.port} · {svc.container}
          </p>
        </div>
        <button
          onClick={() => onRestart(svc.id)}
          disabled={restarting}
          title={`Restart ${svc.name}`}
          className="ml-2 shrink-0 rounded-md p-1.5 text-[var(--chat-muted)] transition-colors hover:bg-[var(--chat-surface)] hover:text-[var(--chat-accent)] disabled:opacity-40"
        >
          {restarting ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <RotateCcw size={14} />
          )}
        </button>
      </div>
      <div className="mt-2">
        <StatusDot healthy={svc.healthy} latency={svc.latency_ms} />
      </div>
      {svc.detail && (
        <p className="mt-1.5 text-[11px] text-[var(--chat-muted)]">{svc.detail}</p>
      )}
    </div>
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
      <div className="mb-6 flex items-center justify-between rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-2.5 text-sm">
        <div className="flex items-center gap-4">
          <span className="text-[var(--chat-muted)]">Services</span>
          {summary.unhealthy === 0 ? (
            <span className="font-medium text-emerald-400">All {summary.total} healthy</span>
          ) : (
            <span className="font-medium text-red-400">
              {summary.unhealthy} unhealthy / {summary.total} total
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-[var(--chat-muted)] transition-colors hover:text-[var(--chat-text)] disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          {refreshedAt ? `Updated ${refreshedAt.toLocaleTimeString()}` : "Loading..."}
        </button>
      </div>

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
        <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-12 text-center">
          <p className="text-sm text-[var(--chat-muted)]">
            Unable to reach backend. Verify the API server is running on the execution node.
          </p>
        </div>
      )}

      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`rounded-lg border px-4 py-2.5 text-sm shadow-lg ${
              t.ok
                ? "border-emerald-800 bg-emerald-950/90 text-emerald-300"
                : "border-red-800 bg-red-950/90 text-red-300"
            }`}
          >
            {t.msg}
          </div>
        ))}
      </div>
    </>
  );
}
