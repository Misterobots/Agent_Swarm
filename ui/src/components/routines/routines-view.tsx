"use client";

import { useState } from "react";
import { ChatView } from "@/components/chat/chat-view";
import { ScheduledRoutines } from "./scheduled-routines";

export function RoutinesView() {
  const [tab, setTab] = useState<"scheduled" | "builder">("scheduled");
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex border-b border-[var(--chat-border)] bg-[var(--chat-surface)] p-1">
        {(["scheduled", "builder"] as const).map((item) => <button key={item} onClick={() => setTab(item)} className={`flex-1 rounded-md px-3 py-2 text-xs font-semibold capitalize ${tab === item ? "bg-[var(--chat-panel)] text-[var(--chat-accent)]" : "text-[var(--chat-muted)]"}`}>{item}</button>)}
      </div>
      <div className="min-h-0 flex-1">{tab === "scheduled" ? <ScheduledRoutines /> : <ChatView experience="routines" />}</div>
    </div>
  );
}
