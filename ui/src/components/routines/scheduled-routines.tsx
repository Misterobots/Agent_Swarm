"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Pause, Play, Plus, RefreshCw, Trash2, X } from "lucide-react";
import {
  createTrigger,
  deleteTrigger,
  listTriggers,
  pauseTrigger,
  resumeTrigger,
  type Trigger,
  type TriggerType,
} from "@/lib/api/triggers";

function scheduleSummary(trigger: Trigger) {
  if (trigger.trigger_type === "cron") {
    const hour = trigger.cron?.hour ?? 0;
    const minute = trigger.cron?.minute ?? 0;
    return `Daily at ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  }
  if (trigger.trigger_type === "interval") return `Every ${trigger.interval_seconds ?? "?"} seconds`;
  return trigger.fire_at ? `Once at ${new Date(trigger.fire_at * 1000).toLocaleString()}` : "One time";
}

export function ScheduledRoutines() {
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await listTriggers();
    setTriggers(result.triggers);
    setError(result.status === 0 ? "Agent Runtime is unreachable." : result.status >= 400 ? `Schedules failed to load (HTTP ${result.status}).` : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const toggle = async (trigger: Trigger) => {
    const ok = trigger.state === "active" ? await pauseTrigger(trigger.trigger_id) : await resumeTrigger(trigger.trigger_id);
    if (ok) void load();
  };

  return (
    <section className="flex h-full flex-col overflow-hidden bg-[var(--chat-bg)]">
      <div className="flex items-center justify-between border-b border-[var(--chat-border)] px-4 py-3">
        <div>
          <h1 className="text-sm font-semibold text-[var(--chat-text)]">Scheduled routines</h1>
          <p className="text-xs text-[var(--chat-muted)]">Saved prompts run by Agent Runtime and survive restarts.</p>
        </div>
        <button onClick={() => setCreating(true)} className="inline-flex items-center gap-1.5 rounded-md bg-[var(--chat-accent)] px-3 py-2 text-xs font-semibold text-white">
          <Plus size={14} /> New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {creating && <RoutineForm onClose={() => setCreating(false)} onCreated={() => { setCreating(false); void load(); }} />}
        {loading && <p className="py-8 text-center text-sm text-[var(--chat-muted)]">Loading schedules…</p>}
        {!loading && error && (
          <div className="flex items-center justify-between rounded-lg border border-red-400/30 bg-red-400/5 p-3 text-sm text-red-400">
            <span>{error}</span><button onClick={() => void load()} aria-label="Retry"><RefreshCw size={15} /></button>
          </div>
        )}
        {!loading && !error && triggers.length === 0 && !creating && (
          <div className="flex flex-col items-center py-14 text-center">
            <CalendarClock size={28} className="mb-3 text-[var(--chat-accent)]" />
            <p className="text-sm font-medium text-[var(--chat-text)]">No scheduled routines yet</p>
            <p className="mt-1 max-w-sm text-xs text-[var(--chat-muted)]">Create a schedule here, or use the Builder tab to develop the prompt first.</p>
          </div>
        )}
        <div className="space-y-2">
          {triggers.map((trigger) => (
            <article key={trigger.trigger_id} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><h2 className="truncate text-sm font-semibold">{trigger.name}</h2><span className="rounded-full border border-[var(--chat-border)] px-1.5 py-0.5 text-[9px] uppercase text-[var(--chat-accent)]">{trigger.state}</span></div>
                  <p className="mt-1 text-xs text-[var(--chat-muted)]">{scheduleSummary(trigger)} · fired {trigger.fire_count}×</p>
                  {trigger.task_config?.prompt && <p className="mt-2 line-clamp-2 text-xs text-[var(--chat-text)]/70">{trigger.task_config.prompt}</p>}
                </div>
                <button onClick={() => void toggle(trigger)} className="p-2 text-[var(--chat-muted)]" aria-label={trigger.state === "active" ? "Pause routine" : "Resume routine"}>{trigger.state === "active" ? <Pause size={15} /> : <Play size={15} />}</button>
                <button onClick={async () => { if (await deleteTrigger(trigger.trigger_id)) void load(); }} className="p-2 text-red-400" aria-label="Delete routine"><Trash2 size={15} /></button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function RoutineForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [type, setType] = useState<TriggerType>("cron");
  const [value, setValue] = useState("8");
  const [minute, setMinute] = useState("0");
  const [swarm, setSwarm] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!name.trim() || !prompt.trim()) return setError("Name and prompt are required.");
    setSaving(true); setError("");
    const timing = type === "cron" ? { cron: { hour: Number(value), minute: Number(minute) } } : type === "interval" ? { interval_seconds: Number(value) } : { delay_seconds: Number(value) };
    const result = await createTrigger({ name: name.trim(), trigger_type: type, task_config: { prompt: prompt.trim(), swarm_mode: swarm }, ...timing });
    setSaving(false);
    if (result.trigger) onCreated(); else setError(result.status === 0 ? "Agent Runtime is unreachable." : `Could not create routine (HTTP ${result.status}).`);
  };

  return (
    <div className="mb-4 space-y-3 rounded-lg border border-[var(--chat-accent)]/40 bg-[var(--chat-surface)] p-3">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">New scheduled routine</h2><button onClick={onClose} aria-label="Close"><X size={15} /></button></div>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Routine name" className="input-field w-full px-3 py-2 text-sm" />
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Prompt to run" rows={3} className="input-field w-full resize-none px-3 py-2 text-sm" />
      <div className="flex gap-2">{(["cron", "interval", "once"] as TriggerType[]).map((item) => <button key={item} onClick={() => { setType(item); setValue(item === "cron" ? "8" : item === "interval" ? "3600" : "60"); }} className={`rounded-md border px-2.5 py-1 text-xs ${type === item ? "border-[var(--chat-accent)] text-[var(--chat-accent)]" : "border-[var(--chat-border)] text-[var(--chat-muted)]"}`}>{item === "cron" ? "Daily" : item === "interval" ? "Repeating" : "One-time"}</button>)}</div>
      <div className="flex items-center gap-2 text-xs text-[var(--chat-muted)]"><span>{type === "cron" ? "At" : type === "interval" ? "Every" : "In"}</span><input type="number" min={type === "cron" ? 0 : 1} max={type === "cron" ? 23 : undefined} value={value} onChange={(e) => setValue(e.target.value)} className="input-field w-20 px-2 py-1" />{type === "cron" ? <><span>:</span><input type="number" min={0} max={59} value={minute} onChange={(e) => setMinute(e.target.value)} className="input-field w-20 px-2 py-1" /></> : <span>seconds</span>}</div>
      <label className="flex items-center gap-2 text-xs text-[var(--chat-muted)]"><input type="checkbox" checked={swarm} onChange={(e) => setSwarm(e.target.checked)} /> Run with Swarm</label>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button onClick={() => void submit()} disabled={saving} className="rounded-md bg-[var(--chat-accent)] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{saving ? "Creating…" : "Create routine"}</button>
    </div>
  );
}
