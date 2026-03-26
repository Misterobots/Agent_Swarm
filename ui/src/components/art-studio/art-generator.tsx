"use client";

import { useState, useEffect, useCallback } from "react";
import { useArtStore, type ArtMode } from "@/lib/stores/art-store";
import { generateImage, generate3D, generateActionFigure, fetchArtModels } from "@/lib/api/art";
import { ImageControls } from "./controls/image-controls";
import { ThreeDControls } from "./controls/three-d-controls";
import { ActionFigureControls } from "./controls/action-figure-controls";
import { GenerationHistory } from "./generation-history";
import { Sparkles, Image, Box, Bone, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";

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
  } = useArtStore();

  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [models, setModels] = useState<string[]>([]);

  // Load models on mount
  useEffect(() => {
    fetchArtModels().then(setModels);
  }, []);

  // Handle prefill from chat redirect
  useEffect(() => {
    if (prefillPrompt) {
      setPrompt(prefillPrompt);
      setPrefillPrompt("");
    }
  }, [prefillPrompt, setPrefillPrompt]);

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
        });
      } else if (mode === "3d") {
        result = await generate3D({
          prompt,
          workflow: threeDSettings.workflow,
          auto_concept: threeDSettings.autoConcept,
        });
      } else {
        result = await generateActionFigure({
          prompt,
          workflow: actionFigureSettings.workflow,
          target_height: actionFigureSettings.targetHeight,
          clearance: actionFigureSettings.clearance,
        });
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
      setPrompt("");
    }
  }, [prompt, mode, isGenerating, imageSettings, threeDSettings, actionFigureSettings, addEntry, updateEntry]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: Controls Panel */}
      <div className="w-72 border-r border-zinc-800 bg-[#0a0a14] flex flex-col overflow-y-auto">
        <div className="p-4">
          <h2 className="text-sm font-semibold text-zinc-300 mb-3">Generation Mode</h2>
          <div className="flex gap-1 bg-zinc-900 rounded-lg p-1">
            {MODES.map((m) => (
              <button
                key={m.key}
                onClick={() => setMode(m.key)}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition-all",
                  mode === m.key
                    ? "bg-violet-600 text-white shadow-lg"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                )}
              >
                <m.icon size={14} />
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-zinc-800" />

        <div className="p-4 flex-1">
          {mode === "image" && <ImageControls models={models} />}
          {mode === "3d" && <ThreeDControls />}
          {mode === "action-figure" && <ActionFigureControls />}
        </div>
      </div>

      {/* Right: Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Prompt Bar */}
        <div className="border-b border-zinc-800 bg-[#0e1117] p-4">
          <div className="flex gap-3 max-w-4xl mx-auto">
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
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
              disabled={isGenerating}
            />
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || isGenerating}
              className={cn(
                "flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all",
                isGenerating
                  ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
                  : "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-900/30"
              )}
            >
              {isGenerating ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
              {isGenerating ? "Generating..." : "Generate"}
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500 gap-4">
              <div className="w-20 h-20 rounded-2xl bg-violet-900/20 flex items-center justify-center">
                <Sparkles size={36} className="text-violet-400" />
              </div>
              <div className="text-center">
                <h2 className="text-lg font-medium text-zinc-300 mb-1">Art Studio</h2>
                <p className="text-sm text-zinc-500">
                  Describe what you want to create and hit Generate
                </p>
                <p className="text-xs text-zinc-600 mt-2">
                  Image generation, 3D models, and posable action figures
                </p>
              </div>
            </div>
          ) : (
            <GenerationHistory entries={history} />
          )}
        </div>
      </div>
    </div>
  );
}
