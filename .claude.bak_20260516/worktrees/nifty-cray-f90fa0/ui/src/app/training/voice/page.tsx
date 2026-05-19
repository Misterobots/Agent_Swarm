"use client";

import { AudioWaveform, Download, Loader2, Play } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
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
          {/* Controls */}
          <Card padding="md">
            <FieldLabel>Pitch Shift</FieldLabel>
            <div className="mt-2 flex items-center gap-3">
              <input
                type="range"
                min={-12}
                max={24}
                value={pitch}
                onChange={(e) => setPitch(Number(e.target.value))}
                className="flex-1 accent-[var(--chat-accent)]"
              />
              <span className="text-[15px] font-semibold tabular-nums text-[var(--chat-text)] w-10 text-right">
                {pitch > 0 ? `+${pitch}` : pitch}
              </span>
            </div>
            <p className="mt-1 text-[10px] text-[var(--chat-subtle)]">semitones</p>

            <div className="mt-5">
              <FieldLabel>Inference Method</FieldLabel>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="input-field mt-2 w-full text-sm"
              >
                <option value="rmvpe">rmvpe</option>
                <option value="pm">pm</option>
                <option value="crepe">crepe</option>
              </select>
            </div>

            <Button
              onClick={onGenerate}
              disabled={!canGenerate}
              variant="primary"
              size="md"
              fullWidth
              loading={loading}
              iconLeft={!loading ? <Play size={14} /> : undefined}
              className="mt-5"
            >
              {loading ? "Synthesizing…" : "Generate Audio"}
            </Button>
          </Card>

          {/* Test phrase + output */}
          <Card padding="md">
            <FieldLabel>Test Phrase</FieldLabel>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              className="input-field mt-2 w-full text-sm leading-relaxed resize-none"
            />
            <div className="mt-4">
              {audioUrl ? (
                <div
                  className="rounded-md p-3"
                  style={{
                    background: "var(--chat-panel)",
                    border: "1px solid var(--chat-border)",
                    boxShadow: "var(--inset-highlight)",
                  }}
                >
                  <FieldLabel>Generated Audio</FieldLabel>
                  <audio src={audioUrl} controls className="mt-2 w-full" />
                  <a
                    href={audioUrl}
                    download={`bmo_pitch_${pitch}.wav`}
                    className="mt-2 inline-flex items-center gap-1.5 text-[12px] font-medium text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)] transition-colors"
                  >
                    <Download size={12} /> Download WAV
                  </a>
                </div>
              ) : (
                <div
                  className="rounded-md border border-dashed border-[var(--chat-border)] px-4 py-6 text-center"
                >
                  <Loader2
                    size={16}
                    className={`mx-auto mb-2 text-[var(--chat-subtle)] ${loading ? "animate-spin" : "opacity-30"}`}
                  />
                  <p className="text-[12px] text-[var(--chat-muted)]">
                    Generate audio to preview calibration output.
                  </p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
      {children}
    </p>
  );
}
