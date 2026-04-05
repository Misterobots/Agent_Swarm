"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import {
  Bot, Cpu, Zap, Flame, Terminal, Rocket, Sparkles, Globe,
  ChevronDown, ChevronUp, Shield, Brain, Search, FileText,
  Palette, Wrench, AlertTriangle, CheckCircle2, Loader2,
  BookOpen, Home, Cog, Eye,
} from "lucide-react";
import { useSettingsStore, type ChatTheme } from "@/lib/stores/settings-store";
import type { PipelineStep } from "@/lib/hooks/use-chat-stream";

/* ── Per-theme thinking word banks ─────────────────────────────────────────── */

const THEMED_VERBS: Record<ChatTheme, string[]> = {
  ember: [
    "Stoking the embers", "Forging a response", "Tempering the logic",
    "Smelting ideas", "Kindling insights", "Fanning the flames",
    "Casting the mold", "Hammering details", "Heating the crucible",
    "Welding concepts", "Sparking connections", "Annealing the answer",
    "Firing up neurons", "Refining the alloy", "Blazing a trail",
  ],
  slate: [
    "Drafting the blueprint", "Sketching a solution", "Laying foundations",
    "Quarrying knowledge", "Carving precision", "Chiseling the response",
    "Polishing the surface", "Smoothing rough edges", "Etching fine details",
    "Stacking the layers", "Aligning the grid", "Leveling the plane",
    "Measuring twice", "Setting the cornerstone", "Calibrating depth",
  ],
  signal: [
    "Tuning the frequency", "Decoding the signal", "Amplifying clarity",
    "Scanning the bandwidth", "Filtering noise", "Locking onto target",
    "Modulating the response", "Broadcasting on all channels", "Parsing the waveform",
    "Boosting the gain", "Triangulating the answer", "Syncing the phase",
    "Reading the spectrum", "Transmitting on frequency", "Homing in",
  ],
  office: [
    "Briefing the team", "Circulating memos", "Consulting the handbook",
    "Cross-referencing files", "Delegating tasks", "Drafting a proposal",
    "Filing paperwork", "Getting sign-off", "Paging the department",
    "Processing the requisition", "Reviewing the dossier", "Running diagnostics",
    "Scheduling a sync", "Sorting the mailroom", "Updating the ledger",
  ],
  hacker: [
    "Injecting payload", "Spawning shell", "Decrypting the matrix",
    "Enumerating targets", "Escalating privileges", "Exploiting the stack",
    "Fuzzing inputs", "Hexdumping memory", "Intercepting packets",
    "Parsing the binary", "Piping through grep", "Reversing the firmware",
    "Root access gained", "SSH tunneling", "Tracing syscalls",
  ],
  "star-trek": [
    "Engaging warp drive", "Scanning for lifeforms", "Hailing Starfleet",
    "Calibrating deflectors", "Consulting the computer", "Diverting power",
    "Loading torpedo bays", "Modulating shields", "Plotting a course",
    "Raising shields", "Reconfiguring the array", "Rerouting through the EPS conduit",
    "Running a Level-3 diagnostic", "Setting course", "Transferring to main screen",
  ],
  cyberpunk: [
    "Jacking into the net", "Running ICE breaker", "Uploading daemon",
    "Decking into cyberspace", "Overclocking wetware", "Parsing braindance",
    "Pinging the Blackwall", "Ripping data shards", "Slicing through firewalls",
    "Splicing neural pathways", "Surfing the datastream", "Syncing cyberware",
    "Tracing the ghost signal", "Unlocking engram", "Zeroing the vector",
  ],
  minimal: [
    "Processing", "Composing", "Analyzing", "Structuring", "Considering",
    "Evaluating", "Formulating", "Reasoning", "Synthesizing", "Thinking",
    "Preparing", "Organizing", "Building", "Computing", "Deriving",
  ],
};

/* ── Per-theme master icons ────────────────────────────────────────────────── */

const THEME_ICON: Record<ChatTheme, typeof Bot> = {
  ember: Flame,
  slate: Cpu,
  signal: Zap,
  office: Bot,
  hacker: Terminal,
  "star-trek": Rocket,
  cyberpunk: Sparkles,
  minimal: Globe,
};

/* ── Agent → icon mapping for pipeline steps ───────────────────────────────── */

const AGENT_ICONS: Record<string, typeof Bot> = {
  "Security Agent": Shield,
  "Security Analysis": Shield,
  "Neural Cortex": Brain,
  "Router": Search,
  "Context Manager": Cog,
  "Memory": Brain,
  "Memory Controller": Brain,
  "JWT-ACE": Shield,
  "Art Director": Palette,
  "Creative Studio": Palette,
  "Technical Writer": FileText,
  "TechnicalWriter": FileText,
  "Librarian": BookOpen,
  "Librarian Agent": BookOpen,
  "Creature Forge": Wrench,
  "Forge": Wrench,
  "IoT Controller": Home,
  "Research": Search,
  "System": Cog,
};

function getAgentIcon(agent: string) {
  return AGENT_ICONS[agent] || Eye;
}

/* ── Phase labels ──────────────────────────────────────────────────────────── */

const PHASE_LABELS: Record<string, string> = {
  thinking: "Reasoning",
  responding: "Generating",
  idle: "Ready",
};

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function pickRandom(arr: string[]): string {
  return arr[Math.floor(Math.random() * arr.length)];
}

function elapsed(ts: number): string {
  const ms = Date.now() - ts;
  if (ms < 1000) return "just now";
  return `${(ms / 1000).toFixed(1)}s ago`;
}

/* ── Component ─────────────────────────────────────────────────────────── */

interface ThinkingIndicatorProps {
  statusMessage: string | null;
  latestThought?: string | null;
  pipelineSteps?: PipelineStep[];
  streamPhase?: "idle" | "thinking" | "responding";
}

export function ThinkingIndicator({
  statusMessage,
  latestThought,
  pipelineSteps = [],
  streamPhase = "thinking",
}: ThinkingIndicatorProps) {
  const theme = useSettingsStore((s) => s.theme);
  const verbs = useMemo(() => THEMED_VERBS[theme] || THEMED_VERBS.ember, [theme]);
  const MasterIcon = THEME_ICON[theme] || Bot;

  const [verb, setVerb] = useState(() => pickRandom(verbs));
  const [expanded, setExpanded] = useState(true);
  const stepsEndRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef(Date.now());

  // Rotate themed verb every 2.8s
  useEffect(() => {
    setVerb(pickRandom(verbs));
    const id = setInterval(() => setVerb(pickRandom(verbs)), 2800);
    return () => clearInterval(id);
  }, [verbs]);

  // Reset start time when pipeline starts fresh
  useEffect(() => {
    if (pipelineSteps.length === 0) {
      startTimeRef.current = Date.now();
    }
  }, [pipelineSteps.length]);

  // Auto-scroll pipeline steps
  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [pipelineSteps.length]);

  const hasSteps = pipelineSteps.length > 0;
  const phaseLabel = PHASE_LABELS[streamPhase] || "Processing";

  return (
    <div className="thinking-container mx-4 my-3 msg-enter">
      <div className="thinking-card rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden shadow-sm">

        {/* ── Header bar ────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 px-4 py-2.5">
          <div className="thinking-icon-ring w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0">
            {streamPhase === "thinking" ? (
              <Loader2 size={16} className="thinking-icon-glow animate-spin" />
            ) : (
              <MasterIcon size={16} className="thinking-icon-glow" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--chat-accent-strong)]">
                {phaseLabel}
              </span>
              <span className="text-[10px] text-[var(--chat-muted)] font-mono">
                {verb}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {hasSteps && (
              <>
                <span className="text-[10px] font-mono text-[var(--chat-muted)]">
                  {pipelineSteps.length} step{pipelineSteps.length !== 1 ? "s" : ""}
                </span>
                <button
                  type="button"
                  onClick={() => setExpanded((e) => !e)}
                  className="p-1 rounded hover:bg-[color:color-mix(in_srgb,var(--chat-accent)_10%,transparent)] text-[var(--chat-muted)] transition-colors"
                  title={expanded ? "Collapse" : "Expand"}
                >
                  {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </>
            )}
            <div className="flex items-center gap-0.5">
              <span className="thinking-dot w-1.5 h-1.5 rounded-full" style={{ animationDelay: "0ms" }} />
              <span className="thinking-dot w-1.5 h-1.5 rounded-full" style={{ animationDelay: "200ms" }} />
              <span className="thinking-dot w-1.5 h-1.5 rounded-full" style={{ animationDelay: "400ms" }} />
            </div>
          </div>
        </div>

        {/* ── Pipeline timeline ─────────────────────────────────────── */}
        {hasSteps && expanded && (
          <div className="pipeline-timeline border-t border-[color:color-mix(in_srgb,var(--chat-border)_50%,transparent)] max-h-64 overflow-y-auto scrollbar-thin">
            <div className="px-3 py-2 space-y-0">
              {pipelineSteps.map((step, idx) => {
                const isLatest = idx === pipelineSteps.length - 1;
                const isError = step.type === "error";
                const StepIcon = getAgentIcon(step.agent);

                return (
                  <div
                    key={step.id}
                    className="pipeline-step-row flex items-start gap-2.5 py-1.5 relative"
                  >
                    {/* Timeline connector line */}
                    {idx < pipelineSteps.length - 1 && (
                      <div className="absolute left-[13px] top-[22px] bottom-0 w-px bg-[color:color-mix(in_srgb,var(--chat-border)_70%,transparent)]" />
                    )}

                    {/* Step icon */}
                    <div
                      className={`relative z-10 w-[26px] h-[26px] rounded-md flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                        isError
                          ? "bg-red-500/15 text-red-400"
                          : isLatest
                          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] text-[var(--chat-accent)]"
                          : "bg-[color:color-mix(in_srgb,var(--chat-border)_30%,transparent)] text-[var(--chat-muted)]"
                      }`}
                    >
                      {isError ? (
                        <AlertTriangle size={13} />
                      ) : isLatest ? (
                        <StepIcon size={13} className="animate-pulse" />
                      ) : (
                        <CheckCircle2 size={13} className="opacity-50" />
                      )}
                    </div>

                    {/* Step content */}
                    <div className="flex-1 min-w-0 pt-0.5">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`text-[11px] font-semibold ${
                            isError
                              ? "text-red-400"
                              : isLatest
                              ? "text-[var(--chat-accent-strong)]"
                              : "text-[var(--chat-text)] opacity-60"
                          }`}
                        >
                          {step.agent}
                        </span>
                        {step.type === "log" && (
                          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-[color:color-mix(in_srgb,var(--chat-accent)_8%,transparent)] text-[var(--chat-muted)]">
                            LOG
                          </span>
                        )}
                      </div>
                      <p
                        className={`text-[11px] leading-snug mt-0.5 ${
                          isLatest
                            ? "text-[var(--chat-text)] opacity-90"
                            : "text-[var(--chat-muted)] opacity-70"
                        }`}
                      >
                        {step.action}
                      </p>
                    </div>

                    {/* Elapsed time for latest step */}
                    {isLatest && (
                      <span className="text-[9px] font-mono text-[var(--chat-muted)] opacity-50 flex-shrink-0 pt-1">
                        {elapsed(step.timestamp)}
                      </span>
                    )}
                  </div>
                );
              })}
              <div ref={stepsEndRef} />
            </div>
          </div>
        )}

        {/* ── Collapsed summary ──────────────────────────────────────── */}
        {hasSteps && !expanded && (
          <div className="border-t border-[color:color-mix(in_srgb,var(--chat-border)_50%,transparent)] px-4 py-1.5">
            <span className="text-[10px] text-[var(--chat-muted)] font-mono">
              {pipelineSteps.length} steps &middot;{" "}
              {pipelineSteps[pipelineSteps.length - 1]?.agent}:{" "}
              {pipelineSteps[pipelineSteps.length - 1]?.action}
            </span>
          </div>
        )}

        {/* ── Progress shimmer bar ───────────────────────────────────── */}
        <div className="thinking-shimmer h-0.5 w-full" />
      </div>
    </div>
  );
}
