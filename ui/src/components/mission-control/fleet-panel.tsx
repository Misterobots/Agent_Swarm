"use client";

import { useCallback, useEffect, useState } from "react";
import { Cpu, FileText, RefreshCw, Server, ShieldAlert, X } from "lucide-react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils/cn";
import {
  clearGpuLock,
  fetchContainerLogs,
  fetchGpuLock,
  restartContainer,
} from "@/lib/api/ops";
import type { ClusterNode, Container, GpuLockStatus } from "@/types/ops";

/**
 * Fleet panel — administer every container across the cluster by (node, name),
 * plus live GPU-lease status with a force-clear. Backs the "Fleet" tab in
 * /mission-control. Container data comes from the parent's /ops/health poll;
 * GPU-lock state is polled here.
 */

const ROLE_LABEL: Record<ClusterNode["role"], string> = {
  gateway: "Gateway",
  control: "Control",
  execution: "Execution",
};

function fmtRemaining(seconds: number | null): string {
  if (seconds == null) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

export function FleetPanel({
  nodes,
  onChanged,
}: {
  nodes: ClusterNode[];
  onChanged?: () => void;
}) {
  const [gpu, setGpu] = useState<GpuLockStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // `${node}/${container}` or "gpu"
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [logs, setLogs] = useState<{
    node: string;
    container: string;
    text: string;
    loading: boolean;
  } | null>(null);

  const loadGpu = useCallback(async () => {
    setGpu(await fetchGpuLock());
  }, []);

  useEffect(() => {
    const initial = setTimeout(() => {
      void loadGpu();
    }, 0);
    const t = setInterval(loadGpu, 5000);
    return () => {
      clearTimeout(initial);
      clearInterval(t);
    };
  }, [loadGpu]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  async function handleRestart(node: string, container: string) {
    if (!window.confirm(`Restart ${container} on ${node}?`)) return;
    setBusy(`${node}/${container}`);
    const res = await restartContainer(node, container);
    setBusy(null);
    const ok = res.status === "restarted";
    setToast({ msg: ok ? `Restarted ${container}` : res.detail || "Restart failed", ok });
    if (ok) setTimeout(() => onChanged?.(), 1500);
  }

  async function handleLogs(node: string, container: string) {
    setLogs({ node, container, text: "", loading: true });
    const res = await fetchContainerLogs(node, container, 300);
    if ("error" in res) {
      setLogs({ node, container, text: `⚠ ${res.error}`, loading: false });
    } else {
      setLogs({ node, container, text: res.logs || "(no output)", loading: false });
    }
  }

  async function handleClearLock() {
    if (!window.confirm("Force-clear the GPU lease? Only do this if a worker is stuck.")) return;
    setBusy("gpu");
    const res = await clearGpuLock();
    setBusy(null);
    const ok = res.status === "cleared" || res.status === "was_free";
    setToast({
      msg: ok ? "GPU lease cleared" : res.detail || "Clear failed",
      ok,
    });
    loadGpu();
  }

  const locked = gpu?.locked === true;
  const gpuUnknown = !gpu || gpu.locked == null;

  return (
    <div className="space-y-5">
      {/* GPU lease widget */}
      <div
        className={cn(
          "flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3",
          "border-[var(--chat-border)] bg-[var(--chat-surface,rgba(255,255,255,0.02))]",
        )}
      >
        <div className="flex items-center gap-3">
          <Cpu
            size={18}
            className={cn(
              locked ? "text-amber-400" : gpuUnknown ? "text-[var(--chat-subtle)]" : "text-emerald-400",
            )}
          />
          <div className="leading-tight">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--chat-subtle)]">
              GPU Lease
            </div>
            <div className="text-sm text-[var(--chat-text)]">
              {gpuUnknown ? (
                <span className="text-[var(--chat-subtle)]">unknown{gpu?.error ? " · host unreachable" : ""}</span>
              ) : locked ? (
                <>
                  <span className="text-amber-400">held</span> by{" "}
                  <span className="font-medium">{gpu?.holder_context || "unknown"}</span> ·{" "}
                  {fmtRemaining(gpu?.remaining_s ?? null)} left
                </>
              ) : (
                <span className="text-emerald-400">free</span>
              )}
            </div>
          </div>
        </div>
        <Button
          variant="danger"
          size="sm"
          iconLeft={<ShieldAlert size={14} />}
          loading={busy === "gpu"}
          disabled={!locked}
          onClick={handleClearLock}
        >
          Force-clear
        </Button>
      </div>

      {/* Per-node container tables */}
      {nodes.map((node) => (
        <div key={node.name} className="rounded-lg border border-[var(--chat-border)]">
          <div className="flex items-center justify-between border-b border-[var(--chat-border)] px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Server size={15} className="text-[var(--chat-subtle)]" />
              <span className="text-sm font-semibold text-[var(--chat-text)]">{node.name}</span>
              <span className="rounded bg-[var(--hover-tint)] px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-[var(--chat-subtle)]">
                {ROLE_LABEL[node.role]}
              </span>
              <span className="text-[11px] text-[var(--chat-subtle)]">{node.ip}</span>
            </div>
            <span
              className={cn(
                "flex items-center gap-1.5 text-[11px]",
                node.healthy ? "text-emerald-400" : "text-red-400",
              )}
            >
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  node.healthy ? "bg-emerald-400" : "bg-red-400",
                )}
              />
              {node.healthy ? `${node.running_count} running` : "unreachable"}
            </span>
          </div>

          {node.healthy ? (
            node.containers.length ? (
              <div className="divide-y divide-[var(--chat-border)]">
                {node.containers.map((c: Container) => (
                  <div
                    key={c.name}
                    className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-[var(--hover-tint)]"
                  >
                    <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-400" />
                    <span className="w-56 shrink-0 truncate font-medium text-[var(--chat-text)]">
                      {c.name}
                    </span>
                    <span className="hidden w-40 shrink-0 truncate text-[12px] text-[var(--chat-subtle)] md:inline">
                      {c.image}
                    </span>
                    <span className="flex-1 truncate text-[12px] text-[var(--chat-subtle)]">
                      {c.uptime}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      iconLeft={<FileText size={13} />}
                      onClick={() => handleLogs(node.name, c.name)}
                    >
                      Logs
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      iconLeft={<RefreshCw size={13} />}
                      loading={busy === `${node.name}/${c.name}`}
                      onClick={() => handleRestart(node.name, c.name)}
                    >
                      Restart
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-4 py-3 text-[13px] text-[var(--chat-subtle)]">No running containers.</div>
            )
          ) : (
            <div className="px-4 py-3 text-[13px] text-red-400">{node.error || "Docker socket unreachable"}</div>
          )}
        </div>
      ))}

      {/* Logs drawer */}
      {logs && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setLogs(null)}
        >
          <div
            className="flex max-h-[80vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-[var(--chat-border)] bg-[var(--chat-bg,#0e1117)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[var(--chat-border)] px-4 py-2.5">
              <span className="text-sm font-semibold text-[var(--chat-text)]">
                {logs.container}{" "}
                <span className="font-normal text-[var(--chat-subtle)]">· {logs.node} · last 300 lines</span>
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="ghost"
                  size="sm"
                  iconLeft={<RefreshCw size={13} />}
                  loading={logs.loading}
                  onClick={() => handleLogs(logs.node, logs.container)}
                >
                  Refresh
                </Button>
                <button
                  onClick={() => setLogs(null)}
                  className="rounded p-1 text-[var(--chat-subtle)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
                  aria-label="Close logs"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto whitespace-pre-wrap break-words p-4 text-[12px] leading-relaxed text-[var(--chat-text)]">
              {logs.loading ? "Loading…" : logs.text}
            </pre>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-6 right-6 z-50 rounded-md border px-4 py-2.5 text-sm shadow-lg",
            toast.ok
              ? "border-emerald-700 bg-emerald-950/90 text-emerald-200"
              : "border-red-700 bg-red-950/90 text-red-200",
          )}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
