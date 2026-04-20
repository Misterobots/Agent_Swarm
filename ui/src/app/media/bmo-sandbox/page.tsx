"use client";

import { useMemo, useRef, useState } from "react";
import { Bot, Loader2, Play, Sparkles, Volume2, Wand2 } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { runBmoSandboxPrompt, synthesizeVoice } from "@/lib/api/workspaces";
import type { BmoSandboxDiagnostics } from "@/types/workspaces";

type SandboxTurn = {
  id: string;
  prompt: string;
  response: string;
  diagnostics: BmoSandboxDiagnostics | null;
  audioUrl: string | null;
  warnings: string[];
};

const QUICK_PROMPTS = [
  "Hey BMO",
  "Tell me a joke",
  "Turn on the living room lights",
  "Are you an AI?",
  "Set the temperature to seventy two degrees",
  "Who wants to play video games?",
];

const FACE_CLASS: Record<string, string> = {
  excited: "before:left-[26%] before:top-[34%] after:right-[26%] after:top-[34%]",
  happy: "before:left-[26%] before:top-[36%] after:right-[26%] after:top-[36%]",
  sad: "before:left-[26%] before:top-[38%] after:right-[26%] after:top-[38%]",
  surprised: "before:left-[24%] before:top-[34%] after:right-[24%] after:top-[34%]",
  sleeping: "before:left-[26%] before:top-[36%] after:right-[26%] after:top-[36%]",
  thinking: "before:left-[26%] before:top-[34%] after:right-[26%] after:top-[40%]",
  error: "before:left-[25%] before:top-[35%] after:right-[25%] after:top-[35%]",
  neutral: "before:left-[26%] before:top-[36%] after:right-[26%] after:top-[36%]",
};

function buildWarnings(response: string, diagnostics: BmoSandboxDiagnostics | null): string[] {
  const warnings: string[] = [];
  if (/[*#`]/.test(response)) warnings.push("Formatting leaked into spoken output.");
  if (/\bAs an AI\b|\blanguage model\b/i.test(response)) warnings.push("Character break detected.");
  if (/\bI\b.*\b(will|am|can|have)\b/.test(response) && !/Beemo/.test(response)) {
    warnings.push("First-person phrasing detected.");
  }
  if (/\d{2,}/.test(response)) warnings.push("Numeric digits present in spoken output.");
  if (/\bBMO\b/.test(response)) warnings.push('"BMO" should be rendered as "Beemo" for speech.');
  if (response.length > 300) warnings.push("Response is longer than ideal for voice playback.");
  if (!diagnostics?.emotion) warnings.push("No emotion metadata returned.");
  return warnings;
}

function faceMood(emotion?: string | null): { label: string; mouthClass: string; eyeClass: string } {
  switch (emotion) {
    case "excited":
      return { label: "Excited", mouthClass: "h-5 w-14 rounded-b-full border-b-4 border-[var(--chat-accent)]", eyeClass: "h-3 w-3 rounded-full bg-[var(--chat-accent)]" };
    case "happy":
      return { label: "Happy", mouthClass: "h-4 w-14 rounded-b-full border-b-4 border-[var(--chat-accent)]", eyeClass: "h-3 w-3 rounded-full bg-[var(--chat-text)]" };
    case "sad":
      return { label: "Sad", mouthClass: "h-4 w-12 rounded-t-full border-t-4 border-[var(--chat-text)]", eyeClass: "h-3 w-3 rounded-full bg-[var(--chat-text)]" };
    case "surprised":
      return { label: "Surprised", mouthClass: "h-6 w-6 rounded-full border-4 border-[var(--chat-accent)]", eyeClass: "h-4 w-4 rounded-full bg-[var(--chat-text)]" };
    case "sleeping":
      return { label: "Sleepy", mouthClass: "h-1.5 w-12 rounded-full bg-[var(--chat-muted)]", eyeClass: "h-0.5 w-6 rounded-full bg-[var(--chat-text)]" };
    case "thinking":
      return { label: "Thinking", mouthClass: "h-2 w-10 rounded-full bg-[var(--chat-accent)]", eyeClass: "h-3 w-3 rounded-full bg-[var(--chat-text)]" };
    case "error":
      return { label: "Glitched", mouthClass: "h-2 w-12 rounded-sm bg-red-400", eyeClass: "h-3 w-3 rotate-45 border-2 border-red-400" };
    default:
      return { label: "Neutral", mouthClass: "h-2 w-12 rounded-full bg-[var(--chat-text)]", eyeClass: "h-3 w-3 rounded-full bg-[var(--chat-text)]" };
  }
}

export default function BmoSandboxPage() {
  const [prompt, setPrompt] = useState("Hey BMO, how are you doing today?");
  const [turns, setTurns] = useState<SandboxTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [method, setMethod] = useState("rmvpe");
  const audioUrlsRef = useRef<string[]>([]);

  const latestTurn = turns[0] ?? null;
  const latestMood = faceMood(latestTurn?.diagnostics?.emotion);
  const facePlacement = FACE_CLASS[latestTurn?.diagnostics?.emotion ?? "neutral"] ?? FACE_CLASS.neutral;

  const totalWarnings = useMemo(
    () => turns.reduce((count, turn) => count + turn.warnings.length, 0),
    [turns]
  );

  async function submitPrompt(nextPrompt: string) {
    const trimmed = nextPrompt.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    try {
      const result = await runBmoSandboxPrompt(trimmed);
      if (!result) {
        console.error("[BMO Sandbox] Empty response from /v1/voice/chat", { prompt: trimmed });
        return;
      }

      let audioUrl: string | null = null;
      const sampleUrl = result.sandbox?.sample_url;
      if (sampleUrl) {
        audioUrl = `/api/backend${sampleUrl}`;
      } else if (ttsEnabled && result.text) {
        const blob = await synthesizeVoice(result.text, Number(result.sandbox?.pitch ?? 3), method);
        if (blob) {
          audioUrl = URL.createObjectURL(blob);
          audioUrlsRef.current.push(audioUrl);
        } else {
          console.error("[BMO Sandbox] Voice synthesis failed", { prompt: trimmed, response: result.text });
        }
      }

      const diagnostics = result.sandbox ?? null;
      const nextTurn: SandboxTurn = {
        id: `${Date.now()}`,
        prompt: trimmed,
        response: result.text,
        diagnostics,
        audioUrl,
        warnings: buildWarnings(result.text, diagnostics),
      };
      setTurns((current) => [nextTurn, ...current].slice(0, 12));
      setPrompt("");
    } catch (error) {
      console.error("[BMO Sandbox] Prompt execution failed", { prompt: nextPrompt, error });
    } finally {
      setLoading(false);
    }
  }

  return (
    <WorkspaceShell
      title="BMO Sandbox"
      description="Browser-based BMO conversation testing with live persona checks, voice playback, and emotion diagnostics."
      icon={Bot}
    >
      <WorkspaceSection title="Live Persona Rig" description="Send prompts through the dedicated BMO voice route and inspect how speech, emotion, and audio selection behave.">
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="rounded-[28px] border border-[var(--chat-border)] bg-[radial-gradient(circle_at_top,_color-mix(in_srgb,var(--chat-accent)_20%,transparent),transparent_55%),var(--chat-panel)] p-5 shadow-[0_20px_80px_-40px_color-mix(in_srgb,var(--chat-accent)_60%,black)]">
            <div className="flex items-center justify-between text-xs uppercase tracking-[0.24em] text-[var(--chat-muted)]">
              <span>Face Preview</span>
              <span>{latestMood.label}</span>
            </div>
            <div className="mt-5 rounded-[32px] border border-[color:color-mix(in_srgb,var(--chat-accent)_30%,transparent)] bg-[linear-gradient(180deg,color-mix(in_srgb,var(--chat-accent)_12%,var(--chat-surface))_0%,var(--chat-surface)_100%)] px-6 py-8">
              <div className="mx-auto w-full max-w-[210px] rounded-[26px] border border-[var(--chat-border)] bg-[#d6f0b8] px-5 py-6 text-slate-900 shadow-inner">
                <div className={`relative mx-auto h-32 w-32 rounded-[20px] border-4 border-slate-900 bg-[#d0f4ff] before:absolute before:h-3 before:w-3 before:rounded-full before:bg-slate-900 after:absolute after:h-3 after:w-3 after:rounded-full after:bg-slate-900 ${facePlacement}`}>
                  <div className="absolute inset-x-0 top-[58%] flex justify-center">
                    <div className={latestMood.mouthClass} />
                  </div>
                  <div className="absolute left-[23%] top-[24%] h-4 w-8 rounded-full border-2 border-slate-900/70" />
                  <div className="absolute right-[23%] top-[24%] h-4 w-8 rounded-full border-2 border-slate-900/70" />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2 text-center text-xs font-medium">
                  <div className="rounded-xl bg-slate-900 px-3 py-2 text-[#d6f0b8]">Pitch {latestTurn?.diagnostics?.pitch ?? 0 >= 0 ? "+" : ""}{latestTurn?.diagnostics?.pitch ?? 0}</div>
                  <div className="rounded-xl bg-slate-900 px-3 py-2 text-[#d6f0b8]">Speed {latestTurn?.diagnostics?.speed?.toFixed(2) ?? "1.00"}x</div>
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-3">
              <div className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[var(--chat-muted)]">Sandbox Summary</p>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-[var(--chat-muted)]">Turns</p>
                    <p className="mt-1 font-semibold text-[var(--chat-text)]">{turns.length}</p>
                  </div>
                  <div>
                    <p className="text-[var(--chat-muted)]">Warnings</p>
                    <p className="mt-1 font-semibold text-[var(--chat-text)]">{totalWarnings}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[var(--chat-muted)]">Playback</p>
                <label className="mt-3 flex items-center justify-between rounded-xl border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-sm text-[var(--chat-text)]">
                  <span>Generate browser audio</span>
                  <input type="checkbox" checked={ttsEnabled} onChange={(e) => setTtsEnabled(e.target.checked)} />
                </label>
                <label className="mt-3 block text-xs text-[var(--chat-muted)]">Synthesis method</label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-sm text-[var(--chat-text)]"
                >
                  <option value="rmvpe">rmvpe</option>
                  <option value="pm">pm</option>
                  <option value="crepe">crepe</option>
                </select>
              </div>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
              <div className="flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((quickPrompt) => (
                  <button
                    key={quickPrompt}
                    onClick={() => {
                      setPrompt(quickPrompt);
                      void submitPrompt(quickPrompt);
                    }}
                    className="rounded-full border border-[var(--chat-border)] bg-[var(--chat-surface)] px-3 py-1.5 text-xs text-[var(--chat-muted)] transition-colors hover:border-[var(--chat-accent)] hover:text-[var(--chat-text)]"
                  >
                    {quickPrompt}
                  </button>
                ))}
              </div>

              <div className="mt-4 rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-bg)] p-4">
                <label className="text-xs uppercase tracking-[0.2em] text-[var(--chat-muted)]">Prompt</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={4}
                  className="mt-2 w-full rounded-xl border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-3 text-sm text-[var(--chat-text)] outline-none focus:border-[var(--chat-accent)]"
                  placeholder="Ask BMO something playful, factual, or smart-home related..."
                />
                <div className="mt-3 flex items-center justify-between gap-3">
                  <p className="text-xs text-[var(--chat-muted)]">The sandbox uses the dedicated BMO voice endpoint, not the general swarm chat route.</p>
                  <button
                    onClick={() => void submitPrompt(prompt)}
                    disabled={loading || !prompt.trim()}
                    className="inline-flex items-center gap-2 rounded-xl border border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/10 px-4 py-2 text-sm text-[var(--chat-accent)] disabled:opacity-50"
                  >
                    {loading ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                    {loading ? "Running..." : "Run Sandbox Turn"}
                  </button>
                </div>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
              <div className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-[var(--chat-text)]">Conversation Trace</p>
                  <Sparkles size={16} className="text-[var(--chat-accent)]" />
                </div>
                <div className="mt-4 space-y-3">
                  {turns.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-8 text-center text-sm text-[var(--chat-muted)]">
                      Run a prompt to inspect BMO&apos;s spoken response, selected audio path, and persona checks.
                    </p>
                  ) : (
                    turns.map((turn) => (
                      <div key={turn.id} className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4">
                        <p className="text-xs uppercase tracking-[0.2em] text-[var(--chat-muted)]">You</p>
                        <p className="mt-2 text-sm text-[var(--chat-text)]">{turn.prompt}</p>
                        <div className="mt-4 rounded-xl border border-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_10%,transparent)] p-4">
                          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[var(--chat-accent)]">
                            <Bot size={14} /> BMO
                          </div>
                          <p className="mt-2 text-sm leading-7 text-[var(--chat-text)]">{turn.response}</p>
                          {turn.audioUrl ? (
                            <div className="mt-4 rounded-xl border border-[var(--chat-border)] bg-[var(--chat-bg)] p-3">
                              <div className="mb-2 flex items-center gap-2 text-xs text-[var(--chat-muted)]">
                                <Volume2 size={14} /> Playback
                              </div>
                              <audio src={turn.audioUrl} controls className="w-full" />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-[var(--chat-text)]">Diagnostics</p>
                  <Play size={16} className="text-[var(--chat-accent)]" />
                </div>
                {latestTurn ? (
                  <div className="mt-4 space-y-3">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3">
                        <p className="text-xs text-[var(--chat-muted)]">Emotion</p>
                        <p className="mt-1 font-semibold text-[var(--chat-text)]">{latestTurn.diagnostics?.emotion ?? "unknown"}</p>
                      </div>
                      <div className="rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3">
                        <p className="text-xs text-[var(--chat-muted)]">Audio Kind</p>
                        <p className="mt-1 font-semibold text-[var(--chat-text)]">{latestTurn.diagnostics?.audio_kind ?? "generated"}</p>
                      </div>
                      <div className="rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3">
                        <p className="text-xs text-[var(--chat-muted)]">Input Sample</p>
                        <p className="mt-1 break-all font-semibold text-[var(--chat-text)]">{latestTurn.diagnostics?.sample_match ?? "none"}</p>
                      </div>
                      <div className="rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3">
                        <p className="text-xs text-[var(--chat-muted)]">Response Sample</p>
                        <p className="mt-1 break-all font-semibold text-[var(--chat-text)]">{latestTurn.diagnostics?.response_sample ?? "none"}</p>
                      </div>
                    </div>

                    <div className="rounded-xl border border-[var(--chat-border)] bg-[var(--chat-surface)] p-4">
                      <p className="text-xs uppercase tracking-[0.2em] text-[var(--chat-muted)]">Persona Checks</p>
                      {latestTurn.warnings.length === 0 ? (
                        <p className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-3 text-sm text-emerald-300">
                          No spoken-output warnings detected for the latest turn.
                        </p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {latestTurn.warnings.map((warning) => (
                            <div key={warning} className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-3 text-sm text-amber-200">
                              {warning}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 rounded-xl border border-dashed border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-8 text-center text-sm text-[var(--chat-muted)]">
                    Diagnostics will appear after the first sandbox turn.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}