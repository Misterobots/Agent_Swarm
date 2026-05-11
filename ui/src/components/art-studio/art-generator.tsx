"use client";

import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useArtStore, type ArtMode } from "@/lib/stores/art-store";
import { generateImage, generate3D, generateActionFigure, fetchArtModels, meshFileUrl } from "@/lib/api/art";
import { ImageControls } from "./controls/image-controls";
import { ThreeDControls } from "./controls/three-d-controls";
import { ActionFigureControls } from "./controls/action-figure-controls";
import { GenerationHistory } from "./generation-history";
import { Sparkles, Image, Box, Bone, Loader2, SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useIsMobile } from "@/lib/hooks/use-mobile";

// Lazy-load the heavy Three.js components
const ModelViewer = lazy(() =>
  import("./model-viewer").then((m) => ({ default: m.ModelViewer }))
);
const JointEditor = lazy(() =>
  import("./joint-editor").then((m) => ({ default: m.JointEditor }))
);

const MODES: { key: ArtMode; label: string; icon: typeof Image }[] = [
  { key: "image", label: "Image", icon: Image },
  { key: "3d", label: "3D Model", icon: Box },
  { key: "action-figure", label: "Action Figure", icon: Bone },
];

export function ArtGenerator() {
  const {
    mode, setMode,
    imageSettings, threeDSettings, actionFigureSettings,
    history, addEntry, updateEntry,
    prefillPrompt, setPrefillPrompt,
    editorMeshPath, setEditorMeshPath,
    clearJoints,
  } = useArtStore();

  const searchParams = useSearchParams();
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [progressMsg, setProgressMsg] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [controlsOpen, setControlsOpen] = useState(false);
  const { isMobile } = useIsMobile();

  // Load models on mount
  useEffect(() => {
    fetchArtModels().then(setModels);
  }, []);

  // Handle prefill from chat redirect (URL param or store)
  useEffect(() => {
    const urlPrompt = searchParams.get("prompt");
    if (urlPrompt) {
      setPrompt(urlPrompt);
    } else if (prefillPrompt) {
      setPrompt(prefillPrompt);
      setPrefillPrompt("");
    }
  }, [searchParams, prefillPrompt, setPrefillPrompt]);

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return;

    const id = crypto.randomUUID();
    addEntry({
      id,
      mode,
      prompt,
      status: "generating",
      timestamp: Date.now(),
    });

    setIsGenerating(true);
    setProgressMsg(null);

    const onProgress = (msg: string) => {
      setProgressMsg(msg);
      updateEntry(id, { result: msg });
    };

    try {
      let result;
      if (mode === "image") {
        result = await generateImage({
          prompt,
          model_name: imageSettings.model,
          cfg: imageSettings.cfg,
          steps: imageSettings.steps,
          width: imageSettings.width,
          height: imageSettings.height,
          sampler: imageSettings.sampler,
          scheduler: imageSettings.scheduler,
          seed: imageSettings.seed,
        }, onProgress);
      } else if (mode === "3d") {
        result = await generate3D({
          prompt,
          workflow: threeDSettings.workflow,
          auto_concept: threeDSettings.autoConcept,
          quality: threeDSettings.quality,
          cfg: { low: 3.0, medium: 5.0, high: 7.0 }[threeDSettings.sourceAdherence],
        }, onProgress);
      } else {
        // Action figure: generate base 3D mesh only (via 3D pipeline),
        // then open the joint editor for user-guided segmentation
        result = await generate3D({
          prompt: `T-pose character, full body, arms to sides, symmetrical: ${prompt}`,
          workflow: actionFigureSettings.workflow,
          auto_concept: true,
        }, onProgress);

        // If mesh generated successfully, extract path and open editor
        if (result.status === "ok" && result.result) {
          const pathMatch = result.result.match(/: (.+\.glb)/);
          if (pathMatch) {
            const meshPath = pathMatch[1];
            updateEntry(id, {
              status: "complete",
              result: result.result,
              meshPath,
            });
            // Open the joint editor with this mesh
            clearJoints();
            setEditorMeshPath(meshPath);
            setIsGenerating(false);
            setProgressMsg(null);
            setPrompt("");
            return;
          }
        }
      }

      updateEntry(id, {
        status: result.status === "ok" ? "complete" : "error",
        result: result.result,
      });
    } catch (err) {
      updateEntry(id, {
        status: "error",
        result: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setIsGenerating(false);
      setProgressMsg(null);
      setPrompt("");
    }
  }, [prompt, mode, isGenerating, imageSettings, threeDSettings, actionFigureSettings, addEntry, updateEntry, setEditorMeshPath, clearJoints]);

  // Whether to show the joint editor (action figure mode with a mesh loaded)
  const showJointEditor = mode === "action-figure" && editorMeshPath;

  const handleEditorBack = useCallback(() => {
    setEditorMeshPath(null);
    clearJoints();
  }, [setEditorMeshPath, clearJoints]);

  const handleSegmentComplete = useCallback((result: string) => {
    addEntry({
      id: crypto.randomUUID(),
      mode: "action-figure",
      prompt: "Segmentation",
      status: result.toLowerCase().includes("error") ? "error" : "complete",
      result,
      timestamp: Date.now(),
    });
    setEditorMeshPath(null);
    clearJoints();
  }, [addEntry, setEditorMeshPath, clearJoints]);

  return (
    <div className="flex flex-col md:flex-row h-full overflow-hidden">
      {/* Mobile controls toggle */}
      {isMobile && !showJointEditor && (
        <button
          onClick={() => setControlsOpen(!controlsOpen)}
          className="relative flex items-center gap-2 px-4 py-2.5 bg-[var(--chat-surface)] text-[13px] font-medium text-[var(--chat-muted)]"
        >
          {controlsOpen ? <X size={15} /> : <SlidersHorizontal size={15} />}
          {controlsOpen ? "Hide Controls" : "Show Controls"}
          <div className="absolute bottom-0 left-0 right-0 divider" />
        </button>
      )}

      {/* Left: Controls / Joint Editor Panel */}
      <div className={cn(
        "border-r border-[var(--chat-border)] bg-[var(--chat-surface)] flex flex-col overflow-y-auto scrollbar-thin",
        isMobile
          ? cn("w-full border-r-0 border-b", controlsOpen ? "max-h-[50vh]" : "max-h-0 overflow-hidden")
          : "w-72"
      )}>
        {showJointEditor ? (
          <Suspense fallback={<div className="p-4 text-[var(--chat-muted)] text-sm">Loading editor…</div>}>
            <JointEditor
              meshPath={editorMeshPath}
              onSegmentComplete={handleSegmentComplete}
              onBack={handleEditorBack}
            />
          </Suspense>
        ) : (
          <>
            <div className="p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)] mb-3">
                Generation Mode
              </p>
              <div
                className="flex gap-1 p-1 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)]"
                style={{ boxShadow: "var(--elev-1), inset 0 1px 2px rgba(0,0,0,0.08)" }}
                role="tablist"
              >
                {MODES.map((m) => (
                  <button
                    key={m.key}
                    role="tab"
                    aria-selected={mode === m.key}
                    onClick={() => setMode(m.key)}
                    className={cn(
                      "flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-sm text-[12px] font-medium transition-all",
                      mode === m.key
                        ? "bg-[var(--chat-elevated)] text-[var(--chat-text)]"
                        : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                    )}
                    style={mode === m.key ? { boxShadow: "var(--elev-1)" } : undefined}
                  >
                    <m.icon size={13} className={mode === m.key ? "text-[var(--chat-accent)]" : ""} />
                    {m.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="divider mx-3" />

            <div className="p-4 flex-1">
              {mode === "image" && <ImageControls models={models} />}
              {mode === "3d" && <ThreeDControls />}
              {mode === "action-figure" && <ActionFigureControls />}
            </div>
          </>
        )}
      </div>

      {/* Right: Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Prompt Bar (hidden when joint editor is open) */}
        {!showJointEditor && (
          <div className="relative bg-[var(--chat-surface)] p-3 md:p-4">
            <div className="flex gap-2 md:gap-3 max-w-4xl mx-auto">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
                placeholder={
                  mode === "image"
                    ? "A cyberpunk samurai in neon rain…"
                    : mode === "3d"
                    ? "A dragon warrior character…"
                    : "A robot action figure with armor plating…"
                }
                className="input-field flex-1 !py-2.5 text-sm"
                disabled={isGenerating}
              />
              <button
                onClick={handleGenerate}
                disabled={!prompt.trim() || isGenerating}
                className={cn(
                  "inline-flex items-center gap-2 px-4 md:px-5 py-2.5 rounded-md text-[13px] font-medium transition-all flex-shrink-0",
                  isGenerating || !prompt.trim() ? "btn-secondary" : "btn-primary"
                )}
              >
                {isGenerating ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Sparkles size={15} />
                )}
                <span className="truncate max-w-[180px]">
                  {isGenerating ? (progressMsg || "Generating…") : "Generate"}
                </span>
              </button>
            </div>
            <div className="absolute bottom-0 left-0 right-0 divider" />
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-hidden">
          {showJointEditor ? (
            <Suspense fallback={
              <div className="flex items-center justify-center h-full text-[var(--chat-muted)]">
                <Loader2 size={24} className="animate-spin mr-2" />
                Loading 3D viewer...
              </div>
            }>
              <ModelViewer url={meshFileUrl(editorMeshPath)} />
            </Suspense>
          ) : (
            <div className="h-full overflow-y-auto p-3 md:p-6">
              {history.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full px-6">
                  <div className="relative mb-6">
                    <div
                      className="w-20 h-20 rounded-2xl flex items-center justify-center"
                      style={{
                        background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 6%, transparent))",
                        border: "1px solid color-mix(in srgb, var(--chat-accent) 30%, var(--chat-border))",
                        boxShadow: "var(--elev-2), inset 0 1px 0 rgba(255,255,255,0.06)",
                      }}
                    >
                      <Sparkles size={36} className="text-[var(--chat-accent)]" />
                    </div>
                    <div
                      className="absolute -inset-4 -z-10 rounded-3xl opacity-60 blur-2xl"
                      style={{ background: "radial-gradient(circle, var(--chat-accent-soft), transparent 70%)" }}
                    />
                  </div>
                  <h2 className="text-2xl font-semibold text-[var(--chat-text)] tracking-tight mb-2">Art Studio</h2>
                  <p className="text-[15px] text-[var(--chat-muted)] text-center">
                    Describe what you want to create and hit Generate.
                  </p>
                  <p className="mt-1 text-[12px] text-[var(--chat-subtle)] text-center">
                    Image generation, 3D models, and posable action figures.
                  </p>
                </div>
              ) : (
                <GenerationHistory entries={history} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
