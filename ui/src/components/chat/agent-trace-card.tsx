"use client";

import { useState } from "react";
import {
  Activity,
  ArrowRight,
  Bot,
  ChevronDown,
  CircleDot,
  FileText,
  Hammer,
  Lightbulb,
  Plus,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { AgentTraceEvent } from "@/types/chat";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map agent names → a consistent accent color class. */
function agentColor(agent: string): string {
  const name = agent.toLowerCase();
  if (name.includes("coordinator") || name.includes("lamport")) return "text-[var(--chat-accent)]";
  if (name.includes("planner") || name.includes("ultra")) return "text-purple-400";
  if (name.includes("verif")) return "text-emerald-400";
  if (name.includes("research")) return "text-sky-400";
  if (name.includes("worker") || name.includes("pioneer")) return "text-amber-400";
  if (name.includes("system") || name.includes("log")) return "text-[var(--chat-muted)]";
  return "text-[var(--chat-accent-strong)]";
}

function agentBg(agent: string): string {
  const name = agent.toLowerCase();
  if (name.includes("coordinator") || name.includes("lamport")) return "bg-[var(--chat-accent-soft)] border-[color-mix(in_srgb,var(--chat-accent)_30%,var(--chat-border))]";
  if (name.includes("planner") || name.includes("ultra")) return "bg-purple-500/10 border-purple-500/30";
  if (name.includes("verif")) return "bg-emerald-500/10 border-emerald-500/30";
  if (name.includes("research")) return "bg-sky-500/10 border-sky-500/30";
  if (name.includes("worker") || name.includes("pioneer")) return "bg-amber-500/10 border-amber-500/30";
  return "bg-[var(--chat-soft)] border-[var(--chat-border)]";
}

type EventType = AgentTraceEvent["eventType"];

function EventIcon({ type, size = 12 }: { type: EventType; size?: number }) {
  switch (type) {
    case "thought":    return <Lightbulb size={size} className="text-[var(--chat-accent)]" />;
    case "status":     return <CircleDot size={size} className="text-[var(--chat-muted)]" />;
    case "tool_call":  return <Wrench size={size} className="text-amber-400" />;
    case "tool_result":return <Hammer size={size} className="text-emerald-400" />;
    case "handoff":    return <ArrowRight size={size} className="text-sky-400" />;
    case "spawned":    return <Plus size={size} className="text-purple-400" />;
    case "log":        return <FileText size={size} className="text-[var(--chat-muted)]" />;
    case "output":     return <FileText size={size} className="text-[var(--chat-subtle)]" />;
    default:           return <Activity size={size} className="text-[var(--chat-muted)]" />;
  }
}

function eventTypeLabel(type: EventType): string {
  switch (type) {
    case "thought":     return "thinking";
    case "status":      return "status";
    case "tool_call":   return "tool";
    case "tool_result": return "result";
    case "handoff":     return "handoff";
    case "spawned":     return "spawned";
    case "log":         return "log";
    case "output":      return "output";
    default:            return type;
  }
}

// Strip leading agent prefix patterns like "→ Coordinator: " or "🧩 Coordinator: "
function cleanContent(content: string): string {
  return content
    .replace(/^[→➜▶•·]\s*([\w\s-]+):\s*/u, "")
    .replace(/^[\p{Emoji}\s]+/u, "")
    .trim();
}

// Unique agent names from the trace
function uniqueAgents(events: AgentTraceEvent[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const e of events) {
    if (!seen.has(e.agent)) { seen.add(e.agent); out.push(e.agent); }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Sub-component: a single trace row
// ---------------------------------------------------------------------------

function TraceRow({ event }: { event: AgentTraceEvent }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = event.content.length > 120;
  const display = isLong && !expanded ? event.content.slice(0, 120) + "…" : event.content;

  return (
    <div className="flex gap-2 py-1 items-start group/row">
      {/* Timestamp */}
      <span className="flex-shrink-0 text-[10px] font-mono text-[var(--chat-subtle)] mt-0.5 w-14">
        {new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>

      {/* Agent chip */}
      <span
        className={cn(
          "flex-shrink-0 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium leading-none mt-0.5",
          agentBg(event.agent)
        )}
      >
        <Bot size={9} className={agentColor(event.agent)} />
        <span className={agentColor(event.agent)}>{event.agent}</span>
      </span>

      {/* Event type icon */}
      <span className="flex-shrink-0 mt-0.5 opacity-70">
        <EventIcon type={event.eventType} size={11} />
      </span>

      {/* Content */}
      <span className="flex-1 min-w-0 text-[11px] leading-relaxed text-[var(--chat-text)] font-mono break-words">
        {display}
        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="ml-1 text-[var(--chat-accent)] hover:underline text-[10px]"
          >
            {expanded ? "show less" : "more"}
          </button>
        )}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface AgentTraceCardProps {
  events: AgentTraceEvent[];
  /** When true the card auto-expands and streams new rows live */
  isStreaming?: boolean;
  /** Controlled from settings: "off" hides everything, "status" shows header only, "full" auto-expands */
  transparency?: "off" | "status" | "full";
}

const VISIBLE_LIMIT = 5;

export function AgentTraceCard({ events, isStreaming, transparency = "status" }: AgentTraceCardProps) {
  const [open, setOpen] = useState(true);
  const [showAll, setShowAll] = useState(false);

  if (transparency === "off" || events.length === 0) return null;

  const agents = uniqueAgents(events);
  const agentSummary = agents.length <= 3 ? agents.join(", ") : `${agents.slice(0, 2).join(", ")} +${agents.length - 2}`;
  const visibleEvents = showAll || events.length <= VISIBLE_LIMIT ? events : events.slice(-VISIBLE_LIMIT);
  const hasMore = !showAll && events.length > VISIBLE_LIMIT;

  return (
    <div className="mt-3 rounded-lg border border-[var(--chat-border)] overflow-hidden text-[12px]">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-[var(--chat-panel)] hover:bg-[var(--chat-soft)] transition-colors text-left"
      >
        <Activity size={12} className="flex-shrink-0 text-[var(--chat-accent)] opacity-80" />
        <span className="font-medium text-[var(--chat-text)]">Agent Stream</span>
        <span className="text-[var(--chat-subtle)]">·</span>
        <span className="text-[var(--chat-muted)]">{events.length} event{events.length !== 1 ? "s" : ""}</span>
        {agents.length > 0 && (
          <>
            <span className="text-[var(--chat-subtle)]">·</span>
            <span className="text-[var(--chat-muted)] truncate max-w-[200px]">{agentSummary}</span>
          </>
        )}
        {/* Live indicator while streaming */}
        {isStreaming && (
          <span
            className="ml-auto flex-shrink-0 w-1.5 h-1.5 rounded-full bg-[var(--chat-accent)] animate-pulse"
            title="Streaming…"
          />
        )}
        <ChevronDown
          size={13}
          className={cn(
            "flex-shrink-0 ml-auto transition-transform duration-150 text-[var(--chat-muted)]",
            isStreaming && "ml-1",  // don't push all the way if live dot is there
            open && "rotate-180"
          )}
        />
      </button>

      {/* Trace rows */}
      {open && (
        <div className="px-3 py-2 bg-[var(--chat-soft)] border-t border-[var(--chat-border)] space-y-0 max-h-[420px] overflow-y-auto">
          {hasMore && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="w-full text-center py-1 text-[10px] text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors border-b border-[var(--chat-border)] mb-1"
            >
              ↑ Show all {events.length} events
            </button>
          )}
          {visibleEvents.map((event, idx) => (
            <TraceRow key={`${event.timestamp}-${idx}`} event={event} />
          ))}
          {isStreaming && (
            <div className="flex items-center gap-1.5 py-1 text-[10px] text-[var(--chat-muted)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--chat-accent)] animate-pulse" />
              streaming…
            </div>
          )}
          {showAll && events.length > VISIBLE_LIMIT && (
            <button
              type="button"
              onClick={() => setShowAll(false)}
              className="w-full text-center py-1 text-[10px] text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors border-t border-[var(--chat-border)] mt-1"
            >
              ↓ Show fewer
            </button>
          )}
        </div>
      )}
    </div>
  );
}
