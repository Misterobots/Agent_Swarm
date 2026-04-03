"use client";

import { useEffect, useState } from "react";
import { Bot } from "lucide-react";

/**
 * Office-themed ambient verbs that rotate while agents work.
 * These show alongside the real backend status message.
 */
const OFFICE_VERBS = [
  "Briefing the team",
  "Brewing a fresh pot",
  "Checking the schedule",
  "Circulating memos",
  "Clearing the inbox",
  "Collating reports",
  "Consulting the handbook",
  "Coordinating departments",
  "Cross-referencing files",
  "Delegating tasks",
  "Dialing into the meeting",
  "Drafting a proposal",
  "Expediting the request",
  "Filing paperwork",
  "Flagging for review",
  "Forwarding to the right desk",
  "Gathering the crew",
  "Getting sign-off",
  "Heading to the war room",
  "Hudding at the whiteboard",
  "Liaising with specialists",
  "Looking up precedents",
  "Making the rounds",
  "Onboarding the task",
  "Paging the department",
  "Penciling it in",
  "Prepping the brief",
  "Processing the requisition",
  "Pulling records",
  "Punching the clock",
  "Putting heads together",
  "Rallying the department",
  "Reviewing the dossier",
  "Routing through channels",
  "Running diagnostics",
  "Running it by management",
  "Scheduling a sync",
  "Sending an internal memo",
  "Shuffling priorities",
  "Sorting the mailroom",
  "Spinning up the bullpen",
  "Stamping approvals",
  "Syncing calendars",
  "Tabulating results",
  "Taking it to committee",
  "Updating the ledger",
  "Water-cooler brainstorming",
  "Working the phones",
];

function pickRandom(): string {
  return OFFICE_VERBS[Math.floor(Math.random() * OFFICE_VERBS.length)];
}

interface ThinkingIndicatorProps {
  statusMessage: string | null;
  latestThought?: string | null;
}

export function ThinkingIndicator({ statusMessage, latestThought }: ThinkingIndicatorProps) {
  const [verb, setVerb] = useState(pickRandom);

  // Rotate the ambient verb every 3 seconds
  useEffect(() => {
    const id = setInterval(() => setVerb(pickRandom()), 3000);
    return () => clearInterval(id);
  }, []);

  // Pick a fresh verb when the real status changes
  useEffect(() => {
    setVerb(pickRandom());
  }, [statusMessage]);

  return (
    <div className="flex gap-3 py-4 px-4 bg-[var(--chat-surface)]">
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-[color:color-mix(in_srgb,var(--chat-accent-2)_14%,transparent)] border border-[var(--chat-border)] flex items-center justify-center">
        <Bot size={16} className="text-[var(--chat-accent-2)] animate-pulse" />
      </div>
      <div className="flex-1 min-w-0">
        {/* Real backend status */}
        {statusMessage && (
          <p className="text-sm text-[var(--chat-text)] mb-1.5">{statusMessage}</p>
        )}
        {latestThought && (
          <p className="text-xs text-[var(--chat-accent-strong)] font-mono mb-1.5">{latestThought}</p>
        )}
        {/* Ambient office verb */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--chat-muted)] italic">{verb}...</span>
          <span className="flex gap-0.5">
            <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:0ms]" />
            <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:150ms]" />
            <span className="w-1 h-1 rounded-full bg-[var(--chat-accent-2)] animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
      </div>
    </div>
  );
}
