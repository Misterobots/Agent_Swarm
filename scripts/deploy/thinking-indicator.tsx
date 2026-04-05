"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { Bot, Cpu, Zap, Flame, Terminal, Rocket, Sparkles, Globe, ChevronDown, ChevronUp } from "lucide-react";
import { useSettingsStore, type ChatTheme } from "@/lib/stores/settings-store";
import type { StreamMode } from "@/types/chat";

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

/* ── Per-theme icons ───────────────────────────────────────────────────────── */

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

/* ── Stream-mode phase labels ──────────────────────────────────────────────── */

const MODE_LABELS: Record<string, string> = {
  thinking: "Thinking",
  responding: "Responding",
  "tool-use": "Using tools",
  requesting: "Requesting",
  compacting: "Compacting context",
};

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function pickRandom(arr: string[]): string {
  return arr[Math.floor(Math.random() * arr.length)];
}

/* ── Step item: extracts agent name + action from a cleaned pipeline line ── */

function parseStep(raw: string): { agent: string; action: string } {
  // Input is already cleaned (no emojis, no markdown).
  // Format: "Security Agent: Scanning input..." or "Router: Intent: AMBIGUOUS"
  const colonIdx = raw.indexOf(":");
  if (colonIdx > 0) {
    const agent = raw.slice(0, colonIdx).trim();
    const action = raw.slice(colonIdx + 1).trim();
    return { agent, action };
  }
  return { agent: "System", action: raw };
}

/* ── Component ─────────────────────────────────────────────────────────────── */

interface ThinkingIndicatorProps {
  statusMessage: string | null;
  latestThought?: string | null;
  pipelineSteps?: string[];
  streamMode?: StreamMode | null;
}

export function ThinkingIndicator({ statusMessage, latestThought, pipelineSteps = [], streamMode }: ThinkingIndicatorProps) {
  const theme = useSettingsStore((s) => s.theme);
  const verbs = useMemo(() => THEMED_VERBS[theme] || THEMED_VERBS.ember, [theme]);
  const Icon = THEME_ICON[theme] || Bot;

  const [verb, setVerb] = useState(() => pickRandom(verbs));
  const [dots, setDots] = useState(1);
  const [expanded, setExpanded] = useState(true);
  const stepsEndRef = useRef<HTMLDivElement>(null);

  // Rotate themed verb every 2.8s
  useEffect(() => {
    setVerb(pickRandom(verbs));
    const id = setInterval(() => setVerb(pickRandom(verbs)), 2800);
    return () => clearInterval(id);
  }, [verbs]);

  // Animate dots
  useEffect(() => {
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 500);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll pipeline steps
  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [pipelineSteps.length]);

  const modeLabel = streamMode ? MODE_LABELS[streamMode] || streamMode : null;
  const hasSteps = pipelineSteps.length > 0;

  return (
    <div className="thinking-container mx-4 my-3 msg-enter">
      <div className="thinking-card rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden">

        {/* Top bar: themed verb + icon */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[color:color-mix(in_srgb,var(--chat-border)_60%,transparent)]">
          <div className="thinking-icon-ring w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0">
            <Icon size={20} className="thinking-icon-glow" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[var(--chat-accent-strong)]">
                {modeLabel || "Processing"}
              </span>
            </div>
            <div className="thinking-verb-display flex items-baseline gap-1 mt-0.5">
              <span className="thinking-verb-text text-xs text-[var(--chat-muted)] tracking-wide">
                {verb}
              </span>
              <span className="text-xs text-[var(--chat-accent)] opacity-70">
                {".".repeat(dots)}
              </span>
            </div>
          </div>
          {/* Expand/collapse + pulse dots */}
          <div className="flex items-center gap-2">
            {hasSteps && (
              <button
                type="button"
                onClick={() => setExpanded((e) => !e)}
                className="p-1 rounded hover:bg-[color:color-mix(in_srgb,var(--chat-accent)_10%,transparent)] text-[var(--chat-muted)] transition-colors"
                title={expanded ? "Collapse reasoning" : "Expand reasoning"}
              >
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            )}
            <div className="flex items-center gap-1">
              <span className="thinking-dot w-2 h-2 rounded-full" style={{ animationDelay: "0ms" }} />
              <span className="thinking-dot w-2 h-2 rounded-full" style={{ animationDelay: "200ms" }} />
              <span className="thinking-dot w-2 h-2 rounded-full" style={{ animationDelay: "400ms" }} />
            </div>
          </div>
        </div>

        {/* ── Pipeline steps: rolling log like Claude/Cursor ────────────── */}
        {hasSteps && expanded && (
          <div className="pipeline-log px-4 py-3 max-h-48 overflow-y-auto scrollbar-thin">
            <div className="space-y-1.5">
              {pipelineSteps.map((step, idx) => {
                const { agent, action } = parseStep(step);
                const isLatest = idx === pipelineSteps.length - 1;
                return (
                  <div
                    key={idx}
                    className={`pipeline-step flex items-start gap-2 text-xs font-mono leading-relaxed transition-opacity duration-300 ${
                      isLatest ? "opacity-100" : "opacity-60"
                    }`}
                    style={{ animationDelay: `${idx * 40}ms` }}
                  >
                    <span className={`pipeline-step-dot w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                      isLatest ? "bg-[var(--chat-accent)] animate-pulse" : "bg-[var(--chat-muted)]"
                    }`} />
                    <span className="text-[var(--chat-accent-strong)] font-semibold whitespace-nowrap">
                      {agent}
                    </span>
                    {action && (
                      <span className="text-[var(--chat-text)] opacity-80 truncate">
                        {action}
                      </span>
                    )}
                  </div>
                );
              })}
              <div ref={stepsEndRef} />
            </div>
          </div>
        )}

        {/* Collapsed summary when pipeline has steps */}
        {hasSteps && !expanded && (
          <div className="px-4 py-2">
            <span className="text-xs text-[var(--chat-muted)] font-mono">
              {pipelineSteps.length} step{pipelineSteps.length !== 1 ? "s" : ""} completed
            </span>
          </div>
        )}

        {/* Thought stream — only show if we have a thought AND no pipeline steps */}
        {!hasSteps && latestThought && (
          <div className="px-4 py-3">
            <div className="thought-stream rounded-lg border border-[color:color-mix(in_srgb,var(--chat-border)_40%,transparent)] bg-[color:color-mix(in_srgb,var(--chat-bg)_80%,transparent)] p-3 max-h-32 overflow-y-auto scrollbar-thin">
              <p className="text-sm font-mono text-[var(--chat-text)] leading-relaxed streaming-caret opacity-90">
                {latestThought}
              </p>
            </div>
          </div>
        )}

        {/* Progress shimmer bar */}
        <div className="thinking-shimmer h-1 w-full" />
      </div>
    </div>
  );
}
