/**
 * @deprecated Thin backwards-compatible facade over the four dev slice stores.
 *
 * Existing consumers that call `useDevStore((s) => s.someField)` continue to
 * work without changes. New code should import from the specific slice directly:
 *
 *   import { useDevEditorStore }  from "@/lib/stores/dev-editor-store";
 *   import { useDevAgentStore }   from "@/lib/stores/dev-agent-store";
 *   import { useDevPanelStore }   from "@/lib/stores/dev-panel-store";
 *   import { useDevProjectStore } from "@/lib/stores/dev-project-store";
 */
"use client";

import { useMemo } from "react";
import { useDevEditorStore, type DevEditorState } from "./dev-editor-store";
import { useDevAgentStore, type DevAgentState } from "./dev-agent-store";
import { useDevPanelStore, type DevPanelState } from "./dev-panel-store";
import { useDevProjectStore, type DevProjectState } from "./dev-project-store";

// Re-export slice types so downstream code that imported DevState from here
// still compiles (they can use CombinedDevState or individual slice types).
export type { DevEditorState } from "./dev-editor-store";
export type { DevAgentState } from "./dev-agent-store";
export type { DevPanelState } from "./dev-panel-store";
export type { DevProjectState } from "./dev-project-store";

export type CombinedDevState = DevEditorState & DevAgentState & DevPanelState & DevProjectState;

/**
 * Backwards-compatible hook.
 *
 * Merges all four slice stores into a single object and applies the selector.
 * Each slice triggers its own re-render, so all four hooks run unconditionally
 * and the result is spread together. The selector is applied to the merged object.
 *
 * If no selector is provided the full merged state is returned.
 */
export function useDevStore(): CombinedDevState;
export function useDevStore<T>(selector: (state: CombinedDevState) => T): T;
export function useDevStore<T>(
  selector?: (state: CombinedDevState) => T
): T | CombinedDevState {
  const editor = useDevEditorStore();
  const agent = useDevAgentStore();
  const panel = useDevPanelStore();
  const project = useDevProjectStore();

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const merged = useMemo<CombinedDevState>(
    () => ({ ...editor, ...agent, ...panel, ...project }),
    // Deliberately broad dep array — all slice states
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editor, agent, panel, project]
  );

  if (selector) return selector(merged);
  return merged;
}

/**
 * Imperative getter (Zustand-compatible `.getState()` pattern).
 *
 * Use this only outside React render (e.g. in event handlers, async callbacks).
 * Inside components, use the `useDevStore` hook instead.
 */
useDevStore.getState = function (): CombinedDevState {
  return {
    ...useDevEditorStore.getState(),
    ...useDevAgentStore.getState(),
    ...useDevPanelStore.getState(),
    ...useDevProjectStore.getState(),
  };
};
