"use client";

import { useEffect, useRef, useState } from "react";
import type { PairingActions, PairingState } from "@/lib/hooks/use-pairing";

type Json = Record<string, unknown>;
type RemoteCadResult = { type: "cad:result"; request_id: string; action: string; ok: true; payload: unknown };
type RemoteCadError = { type: "cad:error"; request_id: string; action?: string; ok: false; error: string };

function asRecord(value: unknown): Json | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Json : null;
}

function requestId() {
  return typeof crypto?.randomUUID === "function"
    ? crypto.randomUUID()
    : `cad-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Guest-only controls for a desktop-owned CAD workstation pairing. */
export function RemoteCadPanel({ state, actions }: { state: PairingState; actions: PairingActions }) {
  const [parts, setParts] = useState<Record<string, { printable?: boolean; material?: string }>>({});
  const [selectedPart, setSelectedPart] = useState("");
  const [buildSet, setBuildSet] = useState<Record<string, number>>({});
  const [jobs, setJobs] = useState<Json[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [printerContext, setPrinterContext] = useState<Json | null>(null);
  const [preflight, setPreflight] = useState<Json | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const pending = useRef(new Map<string, string>());

  useEffect(() => actions.onMessage((message) => {
    if (message.type !== "cad:result" && message.type !== "cad:error") return;
    const reply = message as unknown as RemoteCadResult | RemoteCadError;
    if (!pending.current.has(reply.request_id)) return;
    pending.current.delete(reply.request_id);
    setBusy("");
    if (reply.type === "cad:error") { setError(reply.error); return; }
    setError("");
    setResult(reply.payload);
    const response = asRecord(reply.payload);
    const nextParts = asRecord(response?.parts);
    if (reply.action === "parts" && nextParts) {
      setParts(nextParts as Record<string, { printable?: boolean; material?: string }>);
      setSelectedPart((current) => current || Object.entries(nextParts).find(([, value]) => asRecord(value)?.printable === true)?.[0] || "");
      setBuildSet((current) => Object.keys(current).length ? current : Object.fromEntries(
        Object.entries(nextParts).filter(([, value]) => asRecord(value)?.printable === true).map(([name]) => [name, 0]),
      ));
    }
    if (reply.action === "printer_context") setPrinterContext(response);
    if (reply.action === "print_jobs") {
      const nextJobs = Array.isArray(response?.jobs) ? response.jobs.map(asRecord).filter((job): job is Json => Boolean(job)) : [];
      setJobs(nextJobs);
      setSelectedJob((current) => current || String(nextJobs[0]?.id || ""));
    }
    if (reply.action === "preflight" || reply.action === "request_approval") setPreflight(response);
  }), [actions]);

  const send = (action: string, payload: Record<string, unknown> = {}) => {
    if (state.status !== "connected" || state.role !== "guest") return;
    const id = requestId();
    pending.current.set(id, action);
    setBusy(action);
    setError("");
    actions.send({ type: "cad:request", request_id: id, action, payload });
  };

  if (state.status !== "connected" || state.role !== "guest" || !state.peerCapabilities.includes("cad_review")) return null;
  const printable = Object.entries(parts).filter(([, detail]) => detail.printable);
  const printerEntities = Array.isArray(printerContext?.entities) ? printerContext.entities : [];
  const artifact = asRecord(asRecord(result)?.artifact);
  const buildItems = Object.entries(buildSet).filter(([, quantity]) => quantity > 0).map(([part, quantity]) => ({ part, quantity }));

  return (
    <div className="space-y-2 border-t border-[var(--chat-border)] pt-3">
      <div className="text-xs font-medium text-[var(--chat-text)]">Paired CAD workstation</div>
      <p className="text-[11px] leading-relaxed text-[var(--chat-muted)]">Review and render through the paired desktop. Printer credentials and final print submission remain on that workstation.</p>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => send("parts")} disabled={!!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/50 disabled:opacity-40">{busy === "parts" ? "Loading…" : "Parts"}</button>
        <button onClick={() => send("printer_context")} disabled={!!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/50 disabled:opacity-40">{busy === "printer_context" ? "Checking…" : "Printer"}</button>
      </div>
      {printable.length > 0 && (
        <>
          <div className="flex gap-2">
            <select value={selectedPart} onChange={(event) => setSelectedPart(event.target.value)} className="min-w-0 flex-1 rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] px-2 py-1.5 text-xs text-[var(--chat-text)]">
              {printable.map(([name, detail]) => <option key={name} value={name}>{name}{detail.material ? ` · ${detail.material}` : ""}</option>)}
            </select>
            <button onClick={() => send("render", { part: selectedPart, format: "3mf" })} disabled={!selectedPart || !!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-accent)]/40 text-[var(--chat-accent)] disabled:opacity-40">{busy === "render" ? "Rendering…" : "Render 3MF"}</button>
          </div>
          <div className="space-y-1 rounded border border-[var(--chat-border)]/70 p-2">
            <div className="text-[11px] text-[var(--chat-muted)]">Build set — select source models for Desktop/Orca review.</div>
            {printable.map(([name]) => (
              <label key={name} className="flex items-center gap-2 text-[11px] text-[var(--chat-text)]">
                <input type="checkbox" checked={(buildSet[name] || 0) > 0} onChange={(event) => setBuildSet((current) => ({ ...current, [name]: event.target.checked ? Math.max(1, current[name] || 1) : 0 }))} />
                <span className="min-w-0 flex-1 truncate">{name}</span>
                <input aria-label={`${name} quantity`} type="number" min="1" max="20" value={Math.max(1, buildSet[name] || 1)} disabled={(buildSet[name] || 0) < 1} onChange={(event) => setBuildSet((current) => ({ ...current, [name]: Math.min(20, Math.max(1, Number(event.target.value) || 1)) }))} className="w-12 rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] px-1 py-0.5 text-[11px]" />
              </label>
            ))}
            <button onClick={() => send("export_build_set", { items: buildItems })} disabled={!buildItems.length || !!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-accent)]/40 text-[var(--chat-accent)] disabled:opacity-40">{busy === "export_build_set" ? "Building…" : "Build source package"}</button>
          </div>
        </>
      )}
      <div className="space-y-2 rounded border border-[var(--chat-border)]/70 p-2">
        <div className="flex flex-wrap gap-2">
          <button onClick={() => send("print_jobs")} disabled={!!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/50 disabled:opacity-40">{busy === "print_jobs" ? "Loading…" : "Sliced jobs"}</button>
          <button onClick={() => send("print_status")} disabled={!!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/50 disabled:opacity-40">{busy === "print_status" ? "Checking…" : "Print status"}</button>
        </div>
        {jobs.length > 0 && <div className="flex gap-2">
          <select value={selectedJob} onChange={(event) => { setSelectedJob(event.target.value); setPreflight(null); }} className="min-w-0 flex-1 rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] px-2 py-1.5 text-xs text-[var(--chat-text)]">
            {jobs.map((job) => <option key={String(job.id)} value={String(job.id)}>{String(job.id)} · {String(job.filament || "material not recorded")}</option>)}
          </select>
          <button onClick={() => send("preflight", { job_id: selectedJob })} disabled={!selectedJob || !!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/50 disabled:opacity-40">Preflight</button>
          <button onClick={() => send("request_approval", { job_id: selectedJob })} disabled={!selectedJob || !!busy} className="px-2.5 py-1.5 text-xs rounded border border-[var(--chat-accent)]/40 text-[var(--chat-accent)] disabled:opacity-40">Request approval</button>
        </div>}
        {preflight && <p className="text-[11px] text-[var(--chat-muted)]">{preflight.ok === false ? "Preflight needs attention on Desktop." : "Desktop prepared the review. Final print confirmation remains local."}</p>}
      </div>
      {printerEntities.length > 0 && <p className="text-[11px] text-[var(--chat-muted)]">{printerEntities.map((item) => {
        const entity = asRecord(item);
        const attributes = asRecord(entity?.attributes);
        return `${attributes?.friendly_name || entity?.entity_id || "printer fact"}: ${entity?.state || "unknown"}`;
      }).join(" · ")}</p>}
      {error && <p className="text-[11px] text-red-400">{error}</p>}
      {artifact && <p className="text-[11px] text-green-400">{String(artifact.name || "Source model")} rendered on the paired workstation and ready for its local review workflow.</p>}
    </div>
  );
}
