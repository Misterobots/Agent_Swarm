"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Activity,
  Boxes,
  ClipboardCheck,
  Code2,
  Cpu,
  Database,
  GitBranch,
  HeartPulse,
  LayoutDashboard,
  ListTree,
  Network,
  Palette,
  RefreshCw,
  Search,
  Send,
  Server,
  Sunrise,
  Terminal,
  TrendingUp,
  Wrench,
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
import { streamSSE } from "@/lib/utils/sse-parser";

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

// ── Skills — each tile fires a REAL agentic task into chat (not just a mode) ──
type SkillCat = "Daily" | "Maintenance" | "Memory" | "Research" | "Build";

interface Skill {
  id: string;
  label: string;
  cat: SkillCat;
  icon: LucideIcon;
  command: string; // "" plain · "/swarm" · "/research" · …
  needsInput?: boolean; // uses the typed prompt as the task body
  task?: string; // canned task prompt for zero-input skills
  desc: string;
}

const SKILLS: Skill[] = [
  { id: "brief", label: "Morning Brief", cat: "Daily", icon: Sunrise, command: "",
    task: "Morning brief: overnight swarm runs and their outcomes, any failed containers or unhealthy services, current GPU usage, and the top 3 things worth my attention today.",
    desc: "Overnight status + what needs you" },

  { id: "health", label: "Cluster Health", cat: "Maintenance", icon: Wrench, command: "",
    task: "Run a full cluster health check across Turing, Lovelace, and Hopper — container states, GPU lease, and control-plane service health. Flag anything degraded and recommend fixes.",
    desc: "Nodes, containers, services" },
  { id: "gpu", label: "GPU Audit", cat: "Maintenance", icon: Cpu, command: "",
    task: "Report the current GPU lease status and recent usage across the Ollama nodes; flag anything stuck or contended and whether the lease should be cleared.",
    desc: "Lease + usage" },
  { id: "sweep", label: "Container Sweep", cat: "Maintenance", icon: Boxes, command: "",
    task: "List any stopped or unhealthy containers across the cluster and recommend which to restart.",
    desc: "Stopped / unhealthy" },

  { id: "kbstatus", label: "KB Status", cat: "Memory", icon: HeartPulse, command: "",
    task: "Summarize my MemPalace memory store: total memories, top domains, recent additions, and entity-graph coverage.",
    desc: "Store summary" },
  { id: "cleanup", label: "Memory Cleanup", cat: "Memory", icon: Database, command: "",
    task: "Audit my MemPalace memories for duplicates, stale, or low-value entries and propose a cleanup plan. Do not delete anything without my confirmation.",
    desc: "Dedupe + prune (proposal only)" },
  { id: "recall", label: "Recall Audit", cat: "Memory", icon: Search, command: "",
    task: "Test my memory recall: run several sample queries across my domains and report whether relevant memories surface and under which owner_id.",
    desc: "Verify recall works" },

  { id: "research", label: "Deep Research", cat: "Research", icon: Search, command: "/research", needsInput: true,
    desc: "Multi-source research on a topic (needs a prompt)" },
  { id: "trending", label: "GitHub Trending", cat: "Research", icon: GitBranch, command: "",
    task: "Gather today's trending GitHub projects relevant to LLM agents, inference infrastructure, and homelab automation. Summarize the 5 most relevant to my stack.",
    desc: "Repos worth a look" },
  { id: "radar", label: "Tech Radar", cat: "Research", icon: TrendingUp, command: "",
    task: "Brief me on what's new this week in AI and agent tooling that's relevant to my Memex stack.",
    desc: "This week in AI tooling" },

  { id: "build", label: "Build", cat: "Build", icon: Code2, command: "/swarm", needsInput: true, desc: "Multi-agent build swarm (needs a prompt)" },
  { id: "plan", label: "Plan", cat: "Build", icon: ListTree, command: "/plan", needsInput: true, desc: "Structured planning pass (needs a prompt)" },
  { id: "design", label: "Design", cat: "Build", icon: Palette, command: "/design", needsInput: true, desc: "Generate an HTML mockup (needs a prompt)" },
];

const SKILL_CATS: SkillCat[] = ["Daily", "Maintenance", "Memory", "Research", "Build"];

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
  const [taskRun, setTaskRun] = useState<{ label: string; status: string; output: string; running: boolean } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

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

  async function runInline(label: string, text: string) {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setTaskRun({ label, status: "Running…", output: "", running: true });
    try {
      const resp = await fetch("/api/backend/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "default",
          messages: [{ role: "user", content: text }],
          stream: true,
          session_id: "mc-console",
          memory_enabled: false,
          skill: "general", // forces CONVERSATION → a plain streamed answer in the console
        }),
        signal: ac.signal,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      for await (const ev of streamSSE(resp)) {
        setTaskRun((cur) => {
          if (!cur) return cur;
          if (ev.type === "content" && ev.content) return { ...cur, output: cur.output + ev.content };
          if ((ev.type === "status" || ev.type === "thought") && ev.content) return { ...cur, status: ev.content };
          if (ev.type === "error") return { ...cur, status: "Error", output: cur.output + `\n[error] ${ev.content || ev.errorDetails || ""}` };
          return cur;
        });
      }
    } catch (e) {
      if (!ac.signal.aborted) setTaskRun((cur) => (cur ? { ...cur, output: cur.output + `\n[stream error] ${String(e)}` } : cur));
    } finally {
      setTaskRun((cur) => (cur ? { ...cur, running: false, status: ac.signal.aborted ? "Stopped" : cur.status.startsWith("Error") ? cur.status : "Done" } : cur));
    }
  }

  function fireSkill(skill: Skill) {
    const p = prompt.trim();
    if (skill.needsInput && !p) {
      taRef.current?.focus();
      return;
    }
    const body = skill.needsInput ? p : skill.task || "";
    const text = skill.command ? `${skill.command} ${body}`.trim() : body;
    if (!text) return;
    if (skill.needsInput) {
      // Interactive/creative skills (Build/Plan/Design/Research/Ask) → full chat.
      applyModeForCommand(skill.command);
      useLauncherStore.getState().setPendingLaunch(text);
      router.push("/chat");
    } else {
      // Admin/maintenance/update tasks → run inline; stay in Mission Control.
      runInline(skill.label, text);
    }
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

              {/* Inline task console — admin/maintenance skills stream here, in Mission Control */}
              {taskRun && (
                <Card padding="md">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Terminal size={15} className="shrink-0 text-[var(--chat-accent)]" />
                      <span className="truncate text-sm font-semibold text-[var(--chat-text)]">{taskRun.label}</span>
                      {taskRun.running && <span className="h-2 w-2 shrink-0 rounded-full bg-amber-400 animate-pulse" />}
                      <span className="truncate text-[11px] text-[var(--chat-subtle)]">{taskRun.status}</span>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {taskRun.running && (
                        <Button variant="ghost" size="sm" onClick={() => abortRef.current?.abort()}>Stop</Button>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => { abortRef.current?.abort(); setTaskRun(null); }}>Clear</Button>
                    </div>
                  </div>
                  <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md border border-[var(--chat-border)] bg-[var(--chat-bg)] p-3 text-[13px] leading-relaxed text-[var(--chat-text)]">
                    {taskRun.output || (taskRun.running ? "…" : "(no output)")}
                  </pre>
                </Card>
              )}

              {/* Launcher + recent runs */}
              <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
                <Card padding="md">
                  <div className="text-[11px] uppercase tracking-wide text-[var(--chat-subtle)]">Ready</div>
                  <div className="mt-0.5 text-[17px] font-semibold text-[var(--chat-text)]">Run a skill to begin</div>
                  <textarea
                    ref={taRef}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); const b = SKILLS.find((s) => s.id === "build"); if (b) fireSkill(b); } }}
                    rows={2}
                    placeholder="Type a prompt for Build / Research / Design — or just click a maintenance or memory skill below."
                    className="mt-3 w-full resize-none rounded-md border border-[var(--chat-border)] bg-[var(--chat-bg)] p-2.5 text-[14px] text-[var(--chat-text)] placeholder:text-[var(--chat-subtle)] focus:outline-none focus:ring-1 focus:ring-[var(--chat-accent)]"
                  />
                  <div className="mt-2 flex justify-end">
                    <button
                      onClick={() => fireSkill({ id: "ask", label: "Ask", cat: "Daily", icon: Send, command: "", needsInput: true, desc: "" })}
                      disabled={!prompt.trim()}
                      className={cn("inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium", prompt.trim() ? "bg-[var(--chat-accent)] text-white hover:opacity-90" : "cursor-not-allowed bg-[var(--hover-tint)] text-[var(--chat-subtle)]")}
                    >
                      <Send size={13} /> Ask
                    </button>
                  </div>
                  <div className="mt-3 space-y-3">
                    {SKILL_CATS.map((cat) => {
                      const items = SKILLS.filter((s) => s.cat === cat);
                      if (!items.length) return null;
                      return (
                        <div key={cat}>
                          <div className="mb-1.5 text-[10px] uppercase tracking-wide text-[var(--chat-subtle)]">{cat}</div>
                          <div className="flex flex-wrap gap-2">
                            {items.map((sk) => {
                              const Icon = sk.icon;
                              const disabled = !!sk.needsInput && !prompt.trim();
                              return (
                                <button
                                  key={sk.id}
                                  onClick={() => fireSkill(sk)}
                                  disabled={disabled}
                                  title={sk.desc}
                                  className={cn(
                                    "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[12px] font-medium transition-all",
                                    disabled
                                      ? "cursor-not-allowed border-[var(--chat-border)] text-[var(--chat-subtle)] opacity-50"
                                      : "border-[var(--chat-border)] text-[var(--chat-text)] hover:border-[var(--chat-accent)] hover:bg-[var(--hover-tint)]",
                                  )}
                                >
                                  <Icon size={13} className="text-[var(--chat-accent)]" /> {sk.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
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
