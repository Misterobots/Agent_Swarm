"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

const ROLE_THEME: Record<string, { text: string; bg: string; border: string; stripe: string; accent: string }> = {
  researcher: { text: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30",   stripe: "bg-amber-400",   accent: "#f59e0b" },
  architect:  { text: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/30",    stripe: "bg-blue-400",    accent: "#3b82f6" },
  coder:      { text: "text-violet-400",  bg: "bg-violet-500/10",  border: "border-violet-500/30",  stripe: "bg-violet-400",  accent: "#8b5cf6" },
  devops:     { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", stripe: "bg-emerald-400", accent: "#10b981" },
  analyst:    { text: "text-cyan-400",    bg: "bg-cyan-500/10",    border: "border-cyan-500/30",    stripe: "bg-cyan-400",    accent: "#06b6d4" },
  verifier:   { text: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/30",    stripe: "bg-rose-400",    accent: "#f43f5e" },
};
const DEFAULT_THEME = { text: "text-[var(--chat-muted)]", bg: "bg-[var(--chat-soft)]", border: "border-[var(--chat-border)]", stripe: "bg-[var(--chat-muted)]", accent: "" };

const ROLE_VERB: Record<string, string> = {
  researcher: "Researching", architect: "Designing", coder: "Coding",
  devops: "Deploying", analyst: "Analyzing", verifier: "Verifying",
};

const ROLE_CLEARANCE: Record<string, string> = {
  researcher: "LEVEL 3", architect: "LEVEL 4", coder: "LEVEL 3",
  devops: "LEVEL 5", analyst: "LEVEL 3", verifier: "LEVEL 5",
};

// ─── Pioneer biography data ───────────────────────────────────────────────────
// Keyed by the short pioneer_name emitted by the backend.
// bio = CS background + why they matter to Memex's multi-agent architecture.
const PIONEER_BIOS: Record<string, { cs_role: string; bio: string }> = {
  // Researcher pool
  "Shannon":  { cs_role: "Father of Information Theory", bio: "Claude Shannon published 'A Mathematical Theory of Communication' in 1948, defining entropy, channel capacity, and data encoding. Every AI model's probability distributions—including the sampling strategies Memex uses—are quantified in exactly the terms Shannon formalised." },
  "Minsky":   { cs_role: "AI Pioneer & Cognitive Scientist", bio: "Marvin Minsky co-founded MIT's Artificial Intelligence Laboratory and wrote 'Society of Mind'—the theory that intelligence emerges from many interacting, specialised sub-agents. Memex's multi-agent swarm is a direct software realisation of that vision." },
  "Feynman":  { cs_role: "Physicist & Computation Theorist", bio: "Richard Feynman pioneered the theory of quantum computing and delivered landmark lectures on computation. His habit of decomposing intractable problems into parallel concurrent sub-problems mirrors exactly how Memex's researcher agents attack complex tasks." },
  // Architect pool
  "Babbage":  { cs_role: "Inventor of the Programmable Computer", bio: "Charles Babbage designed the Analytical Engine in the 1830s—the first mechanical general-purpose programmable computer. As computing's original systems architect, his vision of a machine that could execute any algorithm makes him the patron saint of Memex's architect agents." },
  "Dijkstra": { cs_role: "Structured Programming Pioneer", bio: "Edsger Dijkstra invented the shortest-path algorithm, defined structured programming, and wrote seminal proofs of program correctness. Memex's architect agents apply his principle of clean layered decomposition whenever they plan multi-phase task execution." },
  "Brooks":   { cs_role: "Software Engineering Founding Father", bio: "Fred Brooks managed the IBM System/360 project and authored 'The Mythical Man-Month,' establishing software engineering as a discipline. His insight that system complexity must be architecturally managed shaped how Memex serialises dependent implementation tasks." },
  // Coder pool
  "Knuth":    { cs_role: "Author of The Art of Computer Programming", bio: "Donald Knuth wrote the multi-volume 'Art of Computer Programming'—the definitive reference for algorithms—and created the TeX typesetting system. Memex's coder agents stand on Knuth's shoulders whenever they analyse algorithmic complexity or generate precise code." },
  "Lovelace": { cs_role: "World's First Programmer", bio: "Ada Lovelace wrote the first algorithm intended for a computing machine in 1843, foreseeing that Babbage's Analytical Engine could do far more than arithmetic. Memex's coder agents carry her legacy every time they translate a high-level goal into executable instructions." },
  "Ritchie":  { cs_role: "Creator of C and Co-Creator of UNIX", bio: "Dennis Ritchie created the C programming language and co-developed UNIX with Ken Thompson, establishing the foundation for virtually all modern operating systems. The containers running Memex's agent runtime on Turing trace their lineage directly to Ritchie's designs." },
  // DevOps pool
  "Cerf":     { cs_role: "Co-Father of the Internet (TCP/IP)", bio: "Vint Cerf co-designed TCP/IP in the 1970s, giving the internet its fundamental protocols. Memex's devops agents operate on the networked infrastructure Cerf made possible; every streaming API response travels through his protocol." },
  "Torvalds": { cs_role: "Creator of Linux", bio: "Linus Torvalds created the Linux kernel in 1991, which now powers the servers running Memex's Docker containers on Turing. His open-source philosophy also shapes Memex's transparent, community-driven development model." },
  "Thompson": { cs_role: "Co-Creator of UNIX and Go", bio: "Ken Thompson co-created UNIX and the B language, later co-designing Go at Google. His maxim—throw away 1,000 lines of code for a more elegant solution—guides how Memex's devops agents favour minimal, reliable infrastructure over complexity." },
  // Analyst pool
  "Codd":     { cs_role: "Inventor of the Relational Database", bio: "Edgar Codd invented the relational database model and normalisation theory in 1970, establishing how structured data should be stored and queried. Memex's analyst agents apply Codd's relational thinking every time they extract and cross-reference information from multiple sources." },
  "Hopper":   { cs_role: "Creator of the First Compiler", bio: "Grace Hopper created the A-0 compiler—the first program to translate human-readable code into machine instructions—and co-developed COBOL. Her conviction that computers should understand human language directly prefigures how Memex's analyst agents turn natural-language queries into data operations." },
  "Boole":    { cs_role: "Inventor of Boolean Algebra", bio: "George Boole invented Boolean algebra in 1854—the TRUE/FALSE logic underlying every digital circuit and conditional statement. Every branching decision made by a Memex agent is expressed in the calculus Boole formalised." },
  // Verifier pool
  "Hoare":    { cs_role: "Inventor of Hoare Logic & Quicksort", bio: "Tony Hoare invented Hoare Logic—the formal method for proving program correctness—and created the quicksort algorithm. Memex's verifier agents apply his axiomatic reasoning to assert that agent outputs meet stated requirements before synthesis." },
  "Turing":   { cs_role: "Father of Computer Science & AI", bio: "Alan Turing formalised computation itself with the Turing Machine, cracked Enigma during WWII, and posed 'Can machines think?' in 1950. That question is the philosophical north star every Memex agent pursues." },
  "McCarthy": { cs_role: "Coined 'Artificial Intelligence' & Created LISP", bio: "John McCarthy coined the term 'Artificial Intelligence' at the 1956 Dartmouth Conference and invented LISP—the first AI programming language. Memex's verifier agents carry his conviction that machine intelligence can and should be formally specified, tested, and verified." },
};

/** Compact barcode from first 6 chars of worker_id */
function MiniBarcode({ seed }: { seed: string }) {
  const bars = Array.from({ length: 14 }, (_, i) => {
    const c = seed.charCodeAt(i % seed.length) ^ (i * 37);
    return (c % 5 === 0) ? 3 : (c % 3 === 0) ? 1.5 : 0.8;
  });
  return (
    <svg viewBox="0 0 40 10" className="w-10 h-2.5 opacity-25" xmlns="http://www.w3.org/2000/svg">
      {bars.reduce<{ x: number; els: React.ReactElement[] }>(
        ({ x, els }, w, i) => ({
          x: x + w + 0.5,
          els: [...els, i % 2 === 0
            ? <rect key={i} x={x} y={0} width={w} height={10} fill="currentColor" />
            : <rect key={i} x={x} y={0} width={w} height={10} fill="none" />],
        }),
        { x: 0, els: [] }
      ).els}
    </svg>
  );
}

interface AgentRosterProps {
  workers: SwarmWorker[];
  /** When set, only workers in this list are shown (others appear as ghosts). Used during badge spawning. */
  revealedIds?: string[];
}

export function AgentRoster({ workers, revealedIds }: AgentRosterProps) {
  // Track which cards should use the bounce-in animation vs stagger fade-in
  const prevRevealedRef = useRef<Set<string>>(new Set(revealedIds ?? []));
  const [justRevealed, setJustRevealed] = useState<Set<string>>(new Set());
  const [selectedPioneer, setSelectedPioneer] = useState<string | null>(null);

  // When a new ID appears in revealedIds, mark it for the card-enter bounce animation
  useEffect(() => {
    if (!revealedIds) return;
    const newIds = revealedIds.filter((id) => !prevRevealedRef.current.has(id));
    if (newIds.length > 0) {
      setJustRevealed((s) => new Set([...s, ...newIds]));
      prevRevealedRef.current = new Set(revealedIds);
      // Clear "just revealed" after animation completes
      const t = setTimeout(() => setJustRevealed(new Set()), 700);
      return () => clearTimeout(t);
    }
  }, [revealedIds]);

  // Normal roster: stagger all workers in
  const [staggerVisible, setStaggerVisible] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (revealedIds) return; // skip stagger when in badge-spawning mode
    workers.forEach((w, i) => {
      setTimeout(() => setStaggerVisible((s) => new Set([...s, w.worker_id])), i * 120);
    });
  }, [workers, revealedIds]);

  const maxSlots = Math.max(workers.length, 3);
  const slots = workers.length >= maxSlots ? workers : [
    ...workers,
    ...Array.from({ length: maxSlots - workers.length }, (_, i) => ({
      worker_id: `ghost-${i}`, role: "", pioneer_name: "···", pioneer_motto: "",
      task: "", phase: "", state: "pending" as const,
    })),
  ];

  const isSpawning = !!revealedIds;

  return (
    <div className={cn(
      "flex flex-col items-center justify-center gap-4 w-full px-4",
      isSpawning ? "" : "h-full",
    )}>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 w-full max-w-sm">
        {slots.map((w) => {
          const isGhost = w.worker_id.startsWith("ghost-");
          const isRevealed = isSpawning ? (revealedIds!.includes(w.worker_id)) : staggerVisible.has(w.worker_id);
          const isNewlyRevealed = justRevealed.has(w.worker_id);
          const role = w.role?.toLowerCase() ?? "";
          const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
          const isRunning = w.state === "running";
          const badgeNum = w.worker_id.replace(/[^a-z0-9]/gi, "").slice(-6).toUpperCase().padStart(6, "0");
          const stateLabel =
            isRunning ? (ROLE_VERB[role] ?? "Active") :
            w.state === "completed" ? "Done" :
            w.state === "failed" ? "Error" : "Queued";

          return (
            <div
              key={w.worker_id}
              className={cn(
                "flex flex-col rounded-lg overflow-hidden border transition-all",
                "bg-[var(--chat-panel)]",
                isGhost
                  ? "opacity-20 border-[var(--chat-border)]"
                  : isNewlyRevealed
                  ? "[animation:id-card-enter_0.55s_cubic-bezier(.32,1.4,.64,1)_forwards]"
                  : isRevealed
                  ? "opacity-100 translate-y-0 duration-300"
                  : "opacity-0 translate-y-3 duration-300",
                !isGhost && theme.border,
              )}
              style={!isGhost && isRunning && theme.accent
                ? { boxShadow: `0 0 0 1px ${theme.accent}35, 0 0 14px ${theme.accent}20` }
                : undefined}
            >
              {/* Holographic foil stripe */}
              {!isGhost && (
                <div
                  className="h-[3px] w-full flex-shrink-0"
                  style={{ background: `linear-gradient(90deg, transparent 0%, ${theme.accent} 20%, #fff 50%, ${theme.accent} 80%, transparent 100%)`, opacity: 0.75 }}
                />
              )}
              {isGhost && <div className="h-[3px] w-full bg-[var(--chat-border)] flex-shrink-0" />}

              {/* Org mini-header — role-colored tint */}
              {!isGhost && (
                <div
                  className="px-2 py-1 flex items-center justify-between flex-shrink-0"
                  style={{ background: `${theme.accent}14`, borderBottom: `1px solid ${theme.accent}20` }}
                >
                  <span className="text-[6px] font-black tracking-[0.2em] text-white/40 uppercase">Hive Mind</span>
                  <span className="text-[5px] font-mono tracking-widest" style={{ color: `${theme.accent}80` }}>PIONEER</span>
                </div>
              )}

              {/* Photo + Info — horizontal ID-card layout */}
              {!isGhost ? (
                <div className="flex gap-1.5 px-2 pt-2 pb-1.5">
                  {/* Photo */}
                  <div
                    className={cn(
                      "w-9 h-11 rounded-sm border overflow-hidden flex-shrink-0",
                      theme.bg, theme.border, theme.text,
                    )}
                    style={{ boxShadow: `0 0 8px ${theme.accent}25` }}
                  >
                    <PioneerPortrait role={role} />
                  </div>

                  {/* Info column */}
                  <div className="flex flex-col justify-between min-w-0 flex-1 py-0.5">
                    {/* Name — click to show pioneer bio */}
                    <button
                      className="text-[9px] font-bold text-[var(--chat-text)] truncate leading-tight text-left hover:underline focus:outline-none"
                      style={{ color: theme.accent }}
                      onClick={() => setSelectedPioneer(w.pioneer_name)}
                      title="About this pioneer"
                    >
                      {w.pioneer_name}
                    </button>
                    {/* Role badge */}
                    <div
                      className="inline-flex items-center rounded-sm px-1 py-0.5 self-start mt-0.5"
                      style={{ background: `${theme.accent}18`, border: `1px solid ${theme.accent}40` }}
                    >
                      <span
                        className="text-[6.5px] font-bold uppercase tracking-wider"
                        style={{ color: theme.accent }}
                      >
                        {w.role}
                      </span>
                    </div>
                    {/* Clearance */}
                    <p className="text-[6px] font-mono mt-0.5" style={{ color: `${theme.accent}70` }}>
                      {ROLE_CLEARANCE[role] ?? "LEVEL 1"}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="h-12 flex items-center justify-center">
                  <span className="text-[8px] text-[var(--chat-muted)] opacity-30">···</span>
                </div>
              )}

              {/* Status footer */}
              {!isGhost && (
                <div
                  className="px-2 py-1.5 border-t flex items-center justify-between flex-shrink-0"
                  style={{ borderColor: `${theme.accent}18`, background: `${theme.accent}06` }}
                >
                  <div className="flex items-center gap-1">
                    <span
                      className={cn("w-1 h-1 rounded-full flex-shrink-0",
                        w.state === "completed" ? "bg-emerald-400" :
                        isRunning ? cn(theme.stripe, "animate-pulse") :
                        w.state === "failed" ? "bg-red-400" : "bg-[var(--chat-muted)]"
                      )}
                    />
                    <span
                      className={cn(
                        "text-[6px] uppercase tracking-[0.14em] font-semibold truncate",
                        isRunning ? theme.text : "text-[var(--chat-muted)]",
                      )}
                    >
                      {stateLabel}
                    </span>
                  </div>
                  <div className={cn("flex items-center", theme.text)}>
                    <MiniBarcode seed={badgeNum} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {!isSpawning && (
        <p className="text-[11px] text-[var(--chat-muted)] animate-pulse">Assembling swarm&hellip;</p>
      )}

      {/* Pioneer bio modal */}
      {selectedPioneer && (() => {
        const worker = workers.find(w => w.pioneer_name === selectedPioneer);
        const role = worker?.role?.toLowerCase() ?? "";
        const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
        const bio = PIONEER_BIOS[selectedPioneer];
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={() => setSelectedPioneer(null)}
          >
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
            <div
              className="relative z-10 w-full max-w-xs rounded-xl overflow-hidden"
              style={{
                background: "linear-gradient(160deg, var(--chat-panel) 0%, var(--chat-surface,#1a1c2a) 100%)",
                border: `1px solid ${theme.accent}45`,
                boxShadow: `0 24px 64px rgba(0,0,0,0.65), 0 0 0 1px ${theme.accent}20`,
              }}
              onClick={e => e.stopPropagation()}
            >
              {/* Foil stripe */}
              <div
                className="h-1 w-full flex-shrink-0"
                style={{ background: `linear-gradient(90deg, transparent 0%, ${theme.accent} 20%, #fff 50%, ${theme.accent} 80%, transparent 100%)`, opacity: 0.85 }}
              />

              {/* Header */}
              <div
                className="px-4 pt-3 pb-3 flex items-start justify-between gap-2"
                style={{ borderBottom: `1px solid ${theme.accent}20` }}
              >
                <div className="min-w-0">
                  <p className="text-[var(--chat-text)] font-black text-sm leading-tight">
                    {worker?.pioneer_full_name ?? selectedPioneer}
                  </p>
                  {bio && (
                    <p className="text-[9px] font-mono mt-0.5" style={{ color: theme.accent }}>
                      {bio.cs_role}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => setSelectedPioneer(null)}
                  className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
                  style={{ background: `${theme.accent}18` }}
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Bio */}
              <div className="px-4 py-3">
                <p className="text-[11px] text-[var(--chat-muted)] leading-relaxed">
                  {bio?.bio ?? "A pioneering figure in the history of computer science."}
                </p>
              </div>

              {/* Motto */}
              {worker?.pioneer_motto && (
                <div
                  className="mx-4 mb-4 px-2.5 py-1.5 rounded-sm"
                  style={{ background: `${theme.accent}0c`, borderLeft: `2px solid ${theme.accent}50` }}
                >
                  <p className="text-[9px] text-[var(--chat-muted)] italic leading-snug">
                    &ldquo;{worker.pioneer_motto}&rdquo;
                  </p>
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
