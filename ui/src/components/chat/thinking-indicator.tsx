"use client";

import { useEffect, useState } from "react";
import { Bot } from "lucide-react";
import { useSettingsStore, type ChatTheme } from "@/lib/stores/settings-store";
import { THEME_AMBIENT_VERBS } from "@/lib/themes/personalities";

/** Strip all emoji / symbol codepoints from a string. */
function stripEmoji(s: string): string {
  return s
    .replace(
      /[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}\u{2702}-\u{27B0}\u{1F680}-\u{1F6FF}\u{2B50}\u{23CF}\u{23E9}-\u{23F3}\u{23F8}-\u{23FA}\u{25AA}\u{25AB}\u{25B6}\u{25C0}\u{25FB}-\u{25FE}\u{2934}\u{2935}\u{2B05}-\u{2B07}→⏳✅❌]/gu,
      ""
    )
    .replace(/^\s+/, "");
}

/**
 * Extract agent name from backend status message.
 * Handles patterns like:
 * - "⏳ 🔒 Security Agent: Scanning input..."
 * - "🧠 Neural Cortex: Analyzing intent..."
 * - "💬 Hive Mind: Thinking..."
 */
function extractAgentName(raw: string | null): string | null {
  if (!raw) return null;
  const clean = stripEmoji(raw);
  const match = clean.match(/^(.+?):\s/);
  return match ? match[1].trim() : null;
}

/**
 * Extract the agent action/status from backend message.
 * e.g., "Scanning input" from "🔒 Security Agent: Scanning input..."
 */
function extractAgentAction(raw: string | null): string | null {
  if (!raw) return null;
  const clean = stripEmoji(raw);
  const match = clean.match(/:\s*(.+?)\.{0,3}$/);
  return match ? match[1].trim() : null;
}

function pickRandom(list: string[]): string {
  return list[Math.floor(Math.random() * list.length)];
}

interface ThinkingIndicatorProps {
  statusMessage: string | null;
  latestThought?: string | null;
  streamMode?: string | null;
  swarmPhase?: string | null;
}

export function ThinkingIndicator({ statusMessage, latestThought, streamMode, swarmPhase }: ThinkingIndicatorProps) {
  const theme = useSettingsStore((s) => s.theme) as ChatTheme;
  const verbs = THEME_AMBIENT_VERBS[theme] ?? THEME_AMBIENT_VERBS.memex;
  const [verb, setVerb] = useState(() => pickRandom(verbs));
  const [thinkingPhase, setThinkingPhase] = useState(0);

  const isCompacting = streamMode === "compacting";

  const THINKING_PHASES = [
    "Scanning context",
    "Planning response",
    "Composing answer",
    "Validating details",
  ];

  const SWARM_PHASE_LABEL: Record<string, string> = {
    decomposing:   "Decomposing task",
    spawning_card: "Deploying pioneer",
    roster:        "Assembling swarm",
    working:       "Swarm at work",
    synthesizing:  "Synthesizing findings",
  };

  // Rotate the ambient verb every 3 seconds
  useEffect(() => {
    const id = setInterval(() => setVerb(pickRandom(verbs)), 3000);
    return () => clearInterval(id);
  }, [verbs]);

  // Rotate the thinking phase label every 1.6s
  useEffect(() => {
    const id = setInterval(() => setThinkingPhase((p) => (p + 1) % 4), 1600);
    return () => clearInterval(id);
  }, []);

  const agentName = extractAgentName(statusMessage);
  const agentAction = extractAgentAction(statusMessage);

  return (
    <div className="flex gap-3 py-4 px-4 bg-[var(--chat-surface)] msg-enter">
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-[color:color-mix(in_srgb,var(--chat-accent-2)_14%,transparent)] border border-[var(--chat-border)] flex items-center justify-center">
        <Bot size={16} className="text-[var(--chat-accent-2)] animate-pulse" />
      </div>
      <div className="flex-1 min-w-0">
        {/* Compacting override — shown when context window is being summarized */}
        {isCompacting ? (
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-sm font-semibold text-[var(--chat-accent-2)]">
              Compacting context
            </span>
            <span className="flex gap-0.5">
              <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:0ms]" />
              <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:150ms]" />
              <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:300ms]" />
            </span>
          </div>
        ) : (
        <>
        {/* Line 1: Real agent status (stripped of emojis) */}
        <div className="flex items-center gap-2 mb-1.5">
          {agentName ? (
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[var(--chat-accent-strong)]">
                {agentName}
              </span>
              {agentAction && (
                <span className="text-xs text-[var(--chat-muted)]">
                  {agentAction}
                </span>
              )}
            </div>
          ) : swarmPhase && SWARM_PHASE_LABEL[swarmPhase] ? (
            <span className="text-sm font-semibold text-[var(--chat-accent-strong)]">
              {SWARM_PHASE_LABEL[swarmPhase]}
            </span>
          ) : (
            <span className="text-sm font-semibold text-[var(--chat-accent-strong)]">
              {THINKING_PHASES[thinkingPhase]}
            </span>
          )}
          {/* Bouncing dots indicator */}
          <span className="flex gap-0.5">
            <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:0ms]" />
            <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:150ms]" />
            <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
        {/* Line 2: Streaming thought trace */}
        {latestThought && (
          <p className="text-xs text-[var(--chat-accent-strong)] font-mono mb-1.5 thought-stream-text streaming-caret">{latestThought}</p>
        )}
        {/* Line 3: Theme-flavored ambient verb */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--chat-muted)] italic">{verb}...</span>
        </div>
        </>
        )}
      </div>
    </div>
  );
}
