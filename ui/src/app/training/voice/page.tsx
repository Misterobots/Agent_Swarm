"use client";

import { AudioWaveform } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useMemo, useState } from "react";
import { synthesizeVoice } from "@/lib/api/workspaces";

export default function TrainingVoicePage() {
  const [text, setText] = useState("Hello Finn! Check out my new voice calibration.");
  const [pitch, setPitch] = useState(3);
  const [method, setMethod] = useState("rmvpe");
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canGenerate = useMemo(() => text.trim().length > 0 && !loading, [text, loading]);

  async function onGenerate() {
    if (!text.trim()) return;
    setLoading(true);
    const blob = await synthesizeVoice(text.trim(), pitch, method);
    setLoading(false);
    if (!blob) return;
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(URL.createObjectURL(blob));
  }

  return (
    <WorkspaceShell
      title="Voice Calibration"
      description="Calibration surface for BMO voice tuning, playback tests, and inference adjustments."
      icon={AudioWaveform}
    >
      <WorkspaceSection title="Calibration Workspace">
        <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Pitch Shift (Semitones)</p>
            <input
              type="range"
              min={-12}
              max={24}
              value={pitch}
              onChange={(e) => setPitch(Number(e.target.value))}
              className="mt-2 w-full"
            />
            <p className="mt-1 text-sm font-medium text-[var(--chat-text)]">{pitch}</p>

            <p className="mt-4 text-xs text-[var(--chat-muted)]">Inference Method</p>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            >
              <option value="rmvpe">rmvpe</option>
              <option value="pm">pm</option>
              <option value="crepe">crepe</option>
            </select>

            <button
              onClick={onGenerate}
              disabled={!canGenerate}
              className="mt-4 w-full rounded-lg border border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/10 px-3 py-2 text-sm text-[var(--chat-accent)] disabled:opacity-50"
            >
              {loading ? "Synthesizing..." : "Generate Audio"}
            </button>
          </div>

          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]/40 p-4">
            <p className="text-xs text-[var(--chat-muted)]">Test Phrase</p>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              className="mt-1 w-full rounded-lg border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
            />
            {audioUrl ? (
              <div className="mt-4 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-bg)] p-3">
                <p className="mb-2 text-xs text-[var(--chat-muted)]">Generated Audio</p>
                <audio src={audioUrl} controls className="w-full" />
                <a
                  href={audioUrl}
                  download={`bmo_pitch_${pitch}.wav`}
                  className="mt-2 inline-block text-xs text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)]"
                >
                  Download WAV
                </a>
              </div>
            ) : (
              <p className="mt-4 text-xs text-[var(--chat-muted)]">Generate audio to preview calibration output.</p>
            )}
          </div>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}