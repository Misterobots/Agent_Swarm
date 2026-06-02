/**
 * Dev Workspace Panel Registry
 *
 * Panels self-register by calling registerPanel() at module load time.
 * Dev workspace reads the registry to render toolbar buttons and flyout panels.
 *
 * Usage (at the bottom of your panel file):
 *
 *   import { registerPanel } from "./dev-panels-registry";
 *   import { Target } from "lucide-react";
 *   import React from "react";
 *
 *   registerPanel({
 *     id: "goals",
 *     title: "Goals",
 *     position: "right",
 *     icon: React.createElement(Target, { size: 14 }),
 *     component: GoalsPanel,
 *     toolbarOrder: 30,
 *     className: "w-[380px]",
 *   });
 *
 * toolbarOrder slots:
 *   Editor   = 10
 *   Terminal = 20
 *   Goals    = 30
 */

import type { ComponentType } from "react";
import type { ReactNode } from "react";

export interface PanelRegistration {
  /** Unique panel identifier */
  id: string;
  /** Display name shown in toolbar button and flyout header */
  title: string;
  /** Which side the flyout anchors to */
  position: "right" | "bottom";
  /** Icon element for the toolbar button and flyout header */
  icon: ReactNode;
  /** The panel body component (rendered inside the flyout) */
  component: ComponentType;
  /** Lower numbers appear first in the toolbar */
  toolbarOrder: number;
  /** Extra className for the flyout container (e.g. width or height) */
  className?: string;
}

const _registry = new Map<string, PanelRegistration>();

/** Register a panel. Call this once at module load (side-effect import). */
export function registerPanel(registration: PanelRegistration): void {
  _registry.set(registration.id, registration);
}

/** Return all registered panels sorted by toolbarOrder. */
export function getPanels(): PanelRegistration[] {
  return Array.from(_registry.values()).sort(
    (a, b) => a.toolbarOrder - b.toolbarOrder
  );
}

/** Look up a single panel by id. */
export function getPanel(id: string): PanelRegistration | undefined {
  return _registry.get(id);
}
