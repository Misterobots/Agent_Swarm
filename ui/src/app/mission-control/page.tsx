"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Activity,
  Box,
  Boxes,
  BrainCircuit,
  ClipboardCheck,
  Code2,
  Cpu,
  HeartPulse,
  LayoutDashboard,
  ListTree,
  MessagesSquare,
  Network,
  Palette,
  RefreshCw,
  Search,
  Send,
  Server,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { FleetPanel } from "@/components/mission-control/fleet-panel";
import { MaintenanceQueue } from "@/components/mission-control/maintenance-queue";
import { ServiceHealthBody } from "@/components/monitoring/service-health-body";
import { GovernanceWorkflow } from "@/components/governance/governance-workflow";
import {
  fetchOpsHealth,
  fetchGpuLock,
  fetchSwarmSessions,
  fetchSwarmRuns,
  fetchServiceChecks,
} from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import { fetchMaintenanceQueue } from "@/lib/api/maintenance";
import type {
  OpsHealth,
  GpuLockStatus,
  SwarmSession,
  SwarmRun,
  ServiceCheckResponse,
} from "@/types/ops";
import type { GovernanceRequest } from "@/types/workspaces";
import { Button, Card } from "@/components/ui";
import { cn } from "@/lib/utils/cn";
import { useAccess } from "@/lib/hooks/use-access";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useLauncherStore } from "@/lib/stores/launcher-store";

const MemoryGraph3D = dynamic(
  () => import("@/components/graph/memory-graph-3d").then((m) => m.MemoryGraph3D),
  { ssr: false },
);

type TabId = "overview" | "fleet" | "agents" | "memory" | "service-health" | "action-queue";

const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "fleet", label: "Fleet", icon: Server },
  { id: "agents", label: "Agents", icon: Boxes },
  { id: "memory", label: "Memory", icon: Network },
  { id: "service-health", label: "Service Health", icon: HeartPulse },
  { id: "action-queue", label: "Action Queue", icon: ClipboardCheck },
];

// ── Launcher tiles (fire /command into chat) ────────────────────────────────
type ModeId = "swarm" | "plan" | "design" | "cad" | "research" | "workshop" | "think";
const MODES: { id: ModeId; label: string; command: string; icon: LucideIcon; accent: string }[] = [
  { id: "swarm",    label: "Build",    command: "/swarm",    icon: Code2,          accent: "text-cyan-300" },
  { id: "plan",     label: "Plan",     command: "/plan",     icon: ListTree,       accent: "text-emerald-300" },
  { id: "design",   label: "Design",   command: "/design",   icon: Palette,        accent: "text-purple-300" },
  { id: "cad",      label: "CAD",      command: "/cad",      icon: Box,            accent: "text-orange-300" },
  { id: "research", label: "Research", command: "/research", icon: Search,         accent: "text-sky-300" },
  { id: "workshop", label: "Workshop", command: "/workshop", icon: MessagesSquare, accent: "text-amber-300" },
  { id: "think",    label: "Think",    command: "/think",    icon: BrainCircuit,   accent: "text-fuchsia-300" },
];

function applyMode(id: ModeId) {
  const s = useSettingsStore.getState();
  s.setWorkshopMode(false);
  s.setDesignMode(false);
  s.setSwarmMode(false);
  if (id === "workshop") s.setWorkshopMode(true);
  else if (id === "design") s.setDesignMode(true);
  else if (id === "swarm" || id === "plan") s.setSwarmMode(true);
}

function relTime(epochSec?: number): string {
  if (!epochSec) return "—";
  const s = Math.max(0, Math.floor(Date.now() / 1000 - epochSec));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function runStatusColor(status: string): string {
  if (status === "running" || status === "pending") return "bg-amber-400";
  if (status === "failed" || status === "error") return "bg-red-400";
  if (status === "needs_input") return "bg-amber-400";
  return "bg-emerald-400";
}

export default function ControlCenterPage() {
  const router = useRouter();
  const { uid, username } = useAccess();
  const ownerId = username || uid;

  const [tab, setTab] = useState<TabId>("overview");
  const [health, setHealth] = useState<OpsHealth | null>(null);
  const [gpu, setGpu] = useState<GpuLockStatus | null>(null);
  const [sessions, setSessions] = useState<SwarmSession[]>([]);
  const [runs, setRuns] = useState<SwarmRun[]>([]);
  const [services, setServices] = useState<ServiceCheckResponse | null>(null);
  const [requests, setRequests] = useState<GovernanceRequest[]>([]);
  const [pendingMaint, setPendingMaint] = useState(0);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState<Date | null>(null);
  const [prompt, setPrompt] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  async function load() {
    setLoading(true);
    const [h, g, ss, rr, svc, reqs, maint] = await Promise.all([
      fetchOpsHealth(),
      fetchGpuLock(),
      fetchSwarmSessions(),
      fetchSwarmRuns(50),
      fetchServiceChecks(),
      fetchGovernanceRequests(),
      fetchMaintenanceQueue("pending", 200),
    ]);
    setHealth(h);
    setGpu(g);
    setSessions(ss?.sessions ?? []);
    setRuns(rr);
    setServices(svc);
    setRequests(reqs);
    setPendingMaint(maint.length);
    setLoading(false);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const pendingGov = useMemo(
    () => requests.filter((r) => r.status === "PENDING" || r.status === "ASSESSING"),
    [requests],
  );
  const unhealthy = health?.control_plane.filter((s) => !s.healthy) ?? [];
  const actionQueueCount = pendingMaint + pendingGov.length;
  const runningWorkers = sessions.reduce((a, s) => a + (s.running_count || 0), 0);

  // Bucket runs into the last 7 days for the activity spark.
  const activity = useMemo(() => {
    const days: { label: string; count: number }[] = [];
    const dayMs = 86400_000;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    for (let i = 6; i >= 0; i--) {
      const start = today.getTime() - i * dayMs;
      const count = runs.filter((r) => {
        const t = (r.started_at ?? 0) * 1000;
        return t >= start && t < start + dayMs;
      }).length;
      days.push({ label: new Date(start).toLocaleDateString(undefined, { weekday: "short" }), count });
    }
    return days;
  }, [runs]);

  function fireMode(command: string) {
    const p = prompt.trim();
    if (!p) {
      taRef.current?.focus();
      return;
    }
    const id = MODES.find((m) => m.command === command)?.id;
    if (id) applyMode(id);
    useLauncherStore.getState().setPendingLaunch(command ? `${command} ${p}` : p);
    router.push("/chat");
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Ambient 3D memory graph behind the Overview */}
      {tab === "overview" && (
        <>
          <div className="absolute inset-0 z-0">
            <MemoryGraph3D ownerId={ownerId} background />
          </div>
          <div className="pointer-events-none absolute inset-0 z-0" style={{ background: "color-mix(in srgb, var(--chat-bg) 62%, transparent)" }} />
        </>
      )}

      <div className="relative z-10 h-full overflow-y-auto">
        <div className="mx-auto max-w-6xl px-5 py-6">
          {/* Header */}
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <LayoutDashboard size={20} className="text-[var(--chat-accent)]" />
              <div>
                <h1 className="text-lg font-semibold text-[var(--chat-text)]">Control center</h1>
                <p className="text-[12px] text-[var(--chat-muted)]">Unified operator surface · fleet, agents, memory, and skills</p>
              </div>
            </div>
            <div className="flex items-center gap-3 text-[12px] text-[var(--chat-subtle)]">
              <span className="flex items-center gap-1.5">
                <span className={cn("h-2 w-2 rounded-full", unhealthy.length ? "bg-amber-400" : "bg-emerald-400")} />
                {unhealthy.length ? "Degraded" : "Live"}
              </span>
              <span className="hidden sm:inline">{health?.nodes?.length ?? 0} nodes · {health?.running_count ?? 0} containers</span>
              <span className="font-mono tabular-nums">{now ? now.toLocaleTimeString() : "—"}</span>
              <Button variant="secondary" size="sm" onClick={load} iconLeft={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}>
                Refresh
              </Button>
            </div>
          </div>

          {/* Tabs */}
          <div
            role="tablist"
            aria-label="Control center sections"
            className="mb-5 inline-flex flex-wrap items-center gap-1 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)] p-1"
          >
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = tab === t.id;
              const badge =
                t.id === "action-queue" ? actionQueueCount :
                t.id === "service-health" ? unhealthy.length :
                t.id === "agents" ? sessions.length : null;
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-[13px] font-medium transition-all",
                    active ? "bg-[var(--chat-elevated)] text-[var(--chat-text)] shadow-[var(--elev-1)]" : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]",
                  )}
                >
                  <Icon size={14} className={active ? "text-[var(--chat-accent)]" : ""} />
                  {t.label}
                  {badge !== null && badge > 0 && (
                    <span className={cn("rounded-full px-1.5 text-[10px] font-semibold tabular-nums", t.id === "service-health" ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-400")}>
                      {badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {tab === "overview" && (
            <div className="space-y-5">
              {/* Metric tiles */}
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <MetricTile label="Cluster" value={String(health?.running_count ?? 0)} sub={`${health?.nodes?.filter((n) => n.healthy).length ?? 0}/${health?.nodes?.length ?? 0} nodes`} icon={Boxes} tone="neutral" />
                <MetricTile label="Active swarms" value={String(sessions.length)} sub={`${runningWorkers} workers`} icon={Activity} tone={sessions.length ? "accent" : "neutral"} />
                <MetricTile label="GPU lease" value={gpu?.locked ? "Held" : gpu?.locked === false ? "Free" : "—"} sub={gpu?.holder_context || "no holder"} icon={Cpu} tone={gpu?.locked ? "warning" : "success"} />
                <MetricTile label="Services" value={`${services?.summary.healthy ?? 0}/${services?.summary.total ?? 0}`} sub={services && services.summary.unhealthy > 0 ? `${services.summary.unhealthy} down` : "all healthy"} icon={HeartPulse} tone={services && services.summary.unhealthy > 0 ? "warning" : "success"} />
              </div>

              {/* Activity + integrations */}
              <Card padding="md">
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="text-[12px] text-[var(--chat-subtle)]">Swarm activity · 7 days</span>
                  <span className="font-mono text-[11px] text-[var(--chat-muted)]">{runs.length} runs</span>
                </div>
                <ActivitySpark data={activity} />
              </Card>

              {/* Launcher + recent runs */}
              <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
                <Card padding="md">
                  <div className="text-[11px] uppercase tracking-wide text-[var(--chat-subtle)]">Ready</div>
                  <div className="mt-0.5 text-[17px] font-semibold text-[var(--chat-text)]">Run a skill to begin</div>
                  <textarea
                    ref={taRef}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); fireMode("/swarm"); } }}
                    rows={2}
                    placeholder="Type any prompt, then pick a mode…"
                    className="mt-3 w-full resize-none rounded-md border border-[var(--chat-border)] bg-[var(--chat-bg)] p-2.5 text-[14px] text-[var(--chat-text)] placeholder:text-[var(--chat-subtle)] focus:outline-none focus:ring-1 focus:ring-[var(--chat-accent)]"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    {MODES.map((m) => {
                      const Icon = m.icon;
                      return (
                        <button
                          key={m.id}
                          onClick={() => fireMode(m.command)}
                          disabled={!prompt.trim()}
                          title={prompt.trim() ? `Launch ${m.label}` : "Type a prompt first"}
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[12px] font-medium transition-all",
                            prompt.trim()
                              ? "border-[var(--chat-border)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] hover:bg-[var(--hover-tint)]"
                              : "cursor-not-allowed border-[var(--chat-border)] text-[var(--chat-subtle)] opacity-50",
                          )}
                        >
                          <Icon size={13} className={m.accent} /> {m.label}
                          <span className="font-mono text-[10px] text-[var(--chat-subtle)]">{m.command}</span>
                        </button>
                      );
                    })}
                    <button
                      onClick={() => fireMode("")}
                      disabled={!prompt.trim()}
                      className={cn("inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium", prompt.trim() ? "bg-[var(--chat-accent)] text-white hover:opacity-90" : "cursor-not-allowed bg-[var(--hover-tint)] text-[var(--chat-subtle)]")}>
                      <Send size={13} /> Ask
                    </button>
                  </div>
                </Card>

                <Card padding="md">
                  <div className="text-[11px] uppercase tracking-wide text-[var(--chat-subtle)]">Recent runs</div>
                  <div className="mt-3 flex flex-col gap-2.5">
                    {runs.length === 0 && <p className="text-[12px] text-[var(--chat-muted)]">No runs yet. Launch a skill above.</p>}
                    {runs.slice(0, 6).map((r) => (
                      <div key={r.coordination_id} className="flex items-center gap-2 text-[12px]">
                        <span className={cn("h-2 w-2 shrink-0 rounded-full", runStatusColor(r.status))} />
                        <span className="flex-1 truncate text-[var(--chat-text)]">{r.title || r.session_id || r.coordination_id}</span>
                        <span className="font-mono text-[11px] text-[var(--chat-muted)]">{relTime(r.started_at)}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              {/* Integrations strip */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-[var(--chat-subtle)]">Integrations</span>
                {["github", "mempalace", "ollama", "gmail"].map((i) => (
                  <span key={i} className="rounded-md border border-[var(--chat-border)] px-2 py-1 text-[11px] text-[var(--chat-muted)]">{i}</span>
                ))}
              </div>
            </div>
          )}

          {tab === "fleet" && <FleetPanel nodes={health?.nodes || []} onChanged={load} />}

          {tab === "agents" && <AgentsTab sessions={sessions} />}

          {tab === "memory" && (
            <div className="flex h-[70vh] flex-col overflow-hidden rounded-lg border border-[var(--chat-border)]">
              <MemoryGraph3D ownerId={ownerId} />
            </div>
          )}

          {tab === "service-health" && <ServiceHealthBody />}

          {tab === "action-queue" && (
            <div className="space-y-8">
              <section>
                <SubTitle>Maintenance ({pendingMaint})</SubTitle>
                <MaintenanceQueue />
              </section>
              <section>
                <div className="mb-3 flex items-baseline justify-between gap-3">
                  <SubTitle>Governance ({pendingGov.length})</SubTitle>
                  <Link href="/governance" className="text-[12px] text-[var(--chat-accent)] hover:underline">Open in dedicated view →</Link>
                </div>
                <GovernanceWorkflow />
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricTile({ label, value, sub, icon: Icon, tone }: { label: string; value: string; sub: string; icon: LucideIcon; tone: "neutral" | "accent" | "success" | "warning" | "danger" }) {
  const valueClass = { neutral: "text-[var(--chat-text)]", accent: "text-[var(--chat-accent)]", success: "text-emerald-400", warning: "text-amber-400", danger: "text-red-400" }[tone];
  return (
    <Card padding="md">
      <div className="flex items-start justify-between">
        <span className="text-[11px] uppercase tracking-wide text-[var(--chat-subtle)]">{label}</span>
        <Icon size={15} className="text-[var(--chat-muted)]" />
      </div>
      <div className={cn("mt-1.5 text-[24px] font-semibold leading-none tabular-nums", valueClass)}>{value}</div>
      <div className="mt-1.5 text-[11px] text-[var(--chat-muted)]">{sub}</div>
    </Card>
  );
}

function ActivitySpark({ data }: { data: { label: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const w = 100, h = 40;
  const step = data.length > 1 ? w / (data.length - 1) : w;
  const pts = data.map((d, i) => `${(i * step).toFixed(1)},${(h - (d.count / max) * (h - 6) - 3).toFixed(1)}`);
  const area = `0,${h} ${pts.join(" ")} ${w},${h}`;
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-[70px] w-full" role="img" aria-label={`Swarm runs per day over 7 days, ${data.map((d) => d.count).join(", ")}`}>
        <polygon points={area} fill="var(--chat-accent)" opacity="0.12" />
        <polyline points={pts.join(" ")} fill="none" stroke="var(--chat-accent)" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-[var(--chat-subtle)]">
        {data.map((d, i) => <span key={i}>{d.label}</span>)}
      </div>
    </div>
  );
}

function AgentsTab({ sessions }: { sessions: SwarmSession[] }) {
  if (!sessions.length) {
    return (
      <Card padding="lg" className="text-center">
        <Cpu size={22} className="mx-auto mb-2 text-[var(--chat-subtle)]" />
        <p className="text-sm text-[var(--chat-text)]">No active coordinations.</p>
        <p className="mt-1 text-[12px] text-[var(--chat-muted)]">Launch a Build to watch agents here live.</p>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      {sessions.map((s) => (
        <div key={s.coordination_id} className="rounded-lg border border-[var(--chat-border)]">
          <div className="flex items-center justify-between border-b border-[var(--chat-border)] px-4 py-2.5">
            <span className="text-sm font-semibold text-[var(--chat-text)]">{s.session_id}</span>
            <span className="flex items-center gap-1.5 text-[11px] text-amber-400"><span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />{s.running_count} running · {s.worker_count} workers</span>
          </div>
          <div className="divide-y divide-[var(--chat-border)]">
            {s.workers.map((w) => (
              <div key={w.worker_id} className="flex items-center gap-3 px-4 py-2 text-sm">
                <span className="w-28 shrink-0 truncate font-medium text-[var(--chat-text)]">{w.name || w.worker_id}</span>
                <span className="w-24 shrink-0 truncate text-[12px] text-[var(--chat-subtle)]">{w.role}</span>
                <span className="hidden w-32 shrink-0 truncate font-mono text-[11px] text-[var(--chat-accent)] md:inline">{w.model || "—"}</span>
                <span className="flex-1 truncate text-[12px] text-[var(--chat-muted)]">{w.phase}</span>
                <span className={cn("rounded-sm px-1.5 py-0.5 text-[10px] font-semibold uppercase", w.state === "running" ? "bg-amber-500/15 text-amber-400" : w.state === "completed" ? "bg-emerald-500/15 text-emerald-400" : w.state === "failed" ? "bg-red-500/15 text-red-400" : "bg-[var(--hover-tint)] text-[var(--chat-subtle)]")}>{w.state}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SubTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">{children}</h3>;
}
