"use client";

// Landing page — the site's new front door (see plans/peppy-orbiting-honey.md).
// Previously this route just redirected into /chat; the product surface that
// lived behind it now lives in the Desktop app. This page's one job: explain
// what Memex is and get a visitor either downloading the Desktop app or into
// the docs. Admin/ops entry is a quiet corner link, not a primary path.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

/** Continuous 0–1 scroll progress, written straight to a CSS custom property
 * on the landing root (not React state) so it drives pure-CSS effects —
 * background glow, panel charge — at 60fps without a re-render per frame. */
function useScrollIntensity(rootRef: React.RefObject<HTMLElement | null>, reduced: boolean) {
  useEffect(() => {
    if (!rootRef.current) return;
    if (reduced) { rootRef.current.style.setProperty("--intensity", "0.55"); return; }
    // Ramp over min(900px, however far the page actually scrolls) — capped
    // so a long page doesn't drag the ramp out forever, but never longer
    // than what's actually scrollable, so short pages still reach full
    // intensity by the bottom instead of stalling partway.
    let ticking = false;
    const update = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const rampDistance = Math.max(1, Math.min(900, maxScroll));
      const progress = Math.min(1, Math.max(0, window.scrollY / rampDistance));
      rootRef.current?.style.setProperty("--intensity", progress.toFixed(3));
      ticking = false;
    };
    const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); };
  }, [rootRef, reduced]);
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** Reveals children with a fade/rise once scrolled into view. Fires once. */
function useRevealOnScroll<T extends HTMLElement>(reduced: boolean) {
  const ref = useRef<T | null>(null);
  const [visible, setVisible] = useState(reduced);
  useEffect(() => {
    if (reduced || !ref.current) return;
    const el = ref.current;
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); io.unobserve(el); } },
      { threshold: 0.2 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduced]);
  return { ref, visible };
}

function MemexMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size * (32 / 28)} viewBox="0 0 28 32" fill="none" aria-hidden>
      <path d="M14 1L26 8V22L14 29L2 22V8L14 1Z" stroke="var(--chat-accent-strong)" strokeWidth="1.5" fill="color-mix(in srgb, var(--chat-accent) 8%, transparent)" />
      <path d="M14 7L21 11V19L14 23L7 19V11L14 7Z" stroke="var(--chat-accent)" strokeWidth="0.8" opacity="0.5" fill="none" />
      <circle cx="14" cy="15" r="2.5" fill="var(--chat-accent-strong)" opacity="0.7" />
    </svg>
  );
}

// A compact, honest look at the real product surface — the actual roster of
// Pioneers (named after real computer scientists, agents/coordination/pioneers.py),
// the actual app chrome (Workspace/Editor/Tasks), and the real capabilities.
// Not a staged conversation — just what's actually there.
const SHOWCASE_ROSTER = [
  { name: "Lovelace", role: "technical", img: "lovelace" },
  { name: "Turing", role: "systems", img: "turing" },
  { name: "Hopper", role: "user utility", img: "hopper" },
  { name: "Shannon", role: "research", img: "shannon" },
  { name: "Knuth", role: "algorithms", img: "knuth" },
  { name: "Torvalds", role: "infra", img: "torvalds" },
];
const SHOWCASE_FEATURES = [
  "A Coordinator dispatches Pioneers in parallel and reconciles their answers",
  "Scheduled Tasks run the Collective on a cron, unattended",
  "Multi-profile routing across every machine you own",
  "Bring your own models — Ollama, llama.cpp, or both",
];

function AppShowcase({ reduced }: { reduced: boolean }) {
  const { ref, visible } = useRevealOnScroll<HTMLElement>(reduced);
  return (
    <section ref={ref} className={`landing-showcase${visible ? " is-visible" : ""}`}>
      <p className="landing-eyebrow">The actual app</p>
      <h2 className="landing-section-title">A Coordinator, and the Pioneers it dispatches.</h2>
      <div className="landing-app-frame landing-app-frame--compact">
        <div className="landing-app-titlebar">
          <span className="landing-app-dot" aria-hidden />
          <span className="landing-app-dot" aria-hidden />
          <span className="landing-app-dot" aria-hidden />
          <span className="landing-app-tabs">
            <span className="is-active">Workspace</span>
            <span>Editor</span>
            <span>Tasks</span>
          </span>
        </div>
        <div className="landing-app-roster">
          {SHOWCASE_ROSTER.map((p) => (
            <div key={p.name} className="landing-app-roster-card">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/pioneers/${p.img}.png`} alt="" aria-hidden />
              <span className="landing-app-roster-name">{p.name}</span>
              <span className="landing-app-roster-role">{p.role}</span>
            </div>
          ))}
        </div>
      </div>
      <ul className="landing-showcase-features">
        {SHOWCASE_FEATURES.map((f) => <li key={f}>{f}</li>)}
      </ul>
    </section>
  );
}

const PANEL_COPY = [
  {
    title: "Bring your own models",
    body: "Ollama swaps models in and out on demand — good when a run needs several different specialists. llama.cpp pins one model with a disk-persisted context cache — good for one long, latency-critical session. Memex asks which you want; it doesn't decide for you.",
  },
  {
    title: "A Collective, not a chatbot",
    body: "One prompt, several Pioneers — each a distinct perspective on the same question, running in parallel. A Coordinator reconciles what comes back into one answer, instead of you juggling tabs.",
  },
  {
    title: "Your hardware, your data",
    body: "There's no shared backend behind this site anymore. Memex talks directly to the runtime on your own machine — whatever you point it at is the whole system, not a client to someone else's.",
  },
];

function RevealPanel({ title, body, reduced }: { title: string; body: string; reduced: boolean }) {
  const { ref, visible } = useRevealOnScroll<HTMLElement>(reduced);
  return (
    <article ref={ref} className={`landing-panel${visible ? " is-visible" : ""}`}>
      <h2>{title}</h2>
      <p>{body}</p>
    </article>
  );
}

// Grounded in the real trade-off debugged this session (llama-server.yml's
// slot save/restore vs. Ollama's OLLAMA_KEEP_ALIVE lifecycle) — not invented
// marketing bullets.
const ENGINES = [
  {
    name: "Ollama",
    tag: "Swap on demand",
    specs: [
      "Loads/evicts models automatically — OLLAMA_KEEP_ALIVE",
      "Serves many different models across roles in one run",
      "Cold-reload cost paid again after every idle timeout",
    ],
    fit: "A Collective that needs several distinct specialists.",
  },
  {
    name: "llama.cpp",
    tag: "One model, pinned",
    specs: [
      "Disk-persisted context cache — /slots/{id}?action=save|restore",
      "A cache miss at long context means a full re-prefill, so it never misses",
      "Holds exactly one model resident for as long as you need it",
    ],
    fit: "One long, latency-critical session — a big context you can't afford to reload.",
  },
];

function EngineShowcase({ reduced }: { reduced: boolean }) {
  const { ref, visible } = useRevealOnScroll<HTMLElement>(reduced);
  return (
    <section ref={ref} className={`landing-engines${visible ? " is-visible" : ""}`}>
      <p className="landing-eyebrow">Choose your engine</p>
      <h2 className="landing-section-title">Not a decision Memex makes for you.</h2>
      <div className="landing-engine-grid">
        {ENGINES.map((e) => (
          <div key={e.name} className="landing-engine-card">
            <div className="landing-engine-head">
              <span className="landing-engine-name">{e.name}</span>
              <span className="landing-engine-tag">{e.tag}</span>
            </div>
            <ul>
              {e.specs.map((s) => <li key={s}>{s}</li>)}
            </ul>
            <p className="landing-engine-fit"><strong>Best for:</strong> {e.fit}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function LandingPage() {
  const reduced = useReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);
  useScrollIntensity(rootRef, reduced);
  return (
    <div className="landing" ref={rootRef}>
      <div className="landing-circuit-bg" aria-hidden />
      <header className="landing-header">
        <div className="landing-header-inner">
          <div className="landing-brand">
            <MemexMark />
            <span className="landing-wordmark">Memex</span>
          </div>
          <nav className="landing-nav">
            <Link href="/docs">Docs</Link>
            <a href="/api/auth/login">Admin sign in</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="landing-hero landing-hero--single">
          <div className="landing-hero-copy">
            <p className="landing-eyebrow">Local-first agent harness</p>
            <h1 className="landing-headline">
              Your models.<br />Your machine.<br />Your Collective.
            </h1>
            <p className="landing-subhead">
              Memex runs on whatever you already have — Ollama, llama.cpp, or
              both. Ask it something, and a Coordinator dispatches named
              Pioneers to work the problem from different angles, then
              reconciles what they find. No hosted backend, no account
              required, nothing leaves your machine unless you tell it to.
            </p>
            <div className="landing-ctas">
              <Link href="/download" className="landing-cta-primary">Download for Windows</Link>
              <Link href="/docs" className="landing-cta-secondary">Read the docs</Link>
            </div>
            <p className="landing-platform-note">macOS and Linux builds are on the way.</p>
          </div>
        </section>

        <AppShowcase reduced={reduced} />

        <section className="landing-panels">
          {PANEL_COPY.map((p) => (
            <RevealPanel key={p.title} title={p.title} body={p.body} reduced={reduced} />
          ))}
        </section>

        <EngineShowcase reduced={reduced} />
      </main>

      <footer className="landing-footer">
        <span>Memex</span>
        <div className="landing-footer-links">
          <Link href="/docs">Documentation</Link>
          <a href="/api/auth/login">Admin</a>
        </div>
      </footer>
    </div>
  );
}
