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
          className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] text-sm text-[var(--chat-muted)]"
        >
          {controlsOpen ? <X size={16} /> : <SlidersHorizontal size={16} />}
          {controlsOpen ? "Hide Controls" : "Show Controls"}
        </button>
      )}

      {/* Left: Controls / Joint Editor Panel */}
      <div className={cn(
        "border-r border-[var(--chat-border)] bg-[var(--chat-bg)] flex flex-col overflow-y-auto",
        isMobile
          ? cn("w-full border-r-0 border-b", controlsOpen ? "max-h-[50vh]" : "max-h-0 overflow-hidden")
          : "w-72"
      )}>
        {showJointEditor ? (
          <Suspense fallback={<div className="p-4 text-[var(--chat-muted)] text-sm">Loading editor...</div>}>
            <JointEditor
              meshPath={editorMeshPath}
              onSegmentComplete={handleSegmentComplete}
              onBack={handleEditorBack}
            />
          </Suspense>
        ) : (
          <>
            <div className="p-4">
              <h2 className="text-sm font-semibold text-[var(--chat-text)] mb-3">Generation Mode</h2>
              <div className="flex gap-1 bg-[var(--chat-panel)] rounded-lg p-1">
                {MODES.map((m) => (
                  <button
                    key={m.key}
                    onClick={() => setMode(m.key)}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition-all",
                      mode === m.key
                        ? "bg-violet-600 text-white shadow-lg"
                        : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-surface)]"
                    )}
                  >
                    <m.icon size={14} />
                    {m.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-[var(--chat-border)]" />

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
          <div className="border-b border-[var(--chat-border)] bg-[var(--chat-bg)] p-3 md:p-4">
            <div className="flex gap-2 md:gap-3 max-w-4xl mx-auto">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
                placeholder={
                  mode === "image"
                    ? "A cyberpunk samurai in neon rain..."
                    : mode === "3d"
                    ? "A dragon warrior character..."
                    : "A robot action figure with armor plating..."
                }
                className="flex-1 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-4 py-2.5 text-sm text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:outline-none focus:border-violet-500 transition-colors"
                disabled={isGenerating}
              />
              <button
                onClick={handleGenerate}
                disabled={!prompt.trim() || isGenerating}
                className={cn(
                  "flex items-center gap-2 px-3 md:px-5 py-2.5 rounded-lg text-sm font-medium transition-all flex-shrink-0",
                  isGenerating
                    ? "bg-[var(--chat-surface)] text-[var(--chat-muted)] cursor-not-allowed"
                    : "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-900/30"
                )}
              >
                {isGenerating ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                {isGenerating ? (progressMsg || "Generating...") : "Generate"}
              </button>
            </div>
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
                <div className="flex flex-col items-center justify-center h-full text-[var(--chat-muted)] gap-4">
                  <div className="w-20 h-20 rounded-2xl bg-violet-900/20 flex items-center justify-center">
                    <Sparkles size={36} className="text-violet-400" />
                  </div>
                  <div className="text-center">
                    <h2 className="text-lg font-medium text-[var(--chat-text)] mb-1">Art Studio</h2>
                    <p className="text-sm text-[var(--chat-muted)]">
                      Describe what you want to create and hit Generate
                    </p>
                    <p className="text-xs text-[var(--chat-muted)] mt-2">
                      Image generation, 3D models, and posable action figures
                    </p>
                  </div>
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
