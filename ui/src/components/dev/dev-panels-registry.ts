/**
 * Dev Workspace Panel Registry
 *
 * Panels self-register at module scope. dev-workspace.tsx imports the panel
 * files so their registerPanel() side-effects fire, then drives the toolbar
 * and flyouts from getRegisteredPanels().
 *
 * Reserved toolbarOrder slots:
 *   10 — Editor (built-in)
 *   20 — Terminal (built-in)
 *   30 — Goals (Q5)
 *   40–90 — available for future panels
 *
 * Usage in a panel file:
 * ```ts
 * import { registerPanel } from "./dev-panels-registry";
 * import { SomeIcon } from "lucide-react";
 *
 * registerPanel({
 *   id: "your-panel",
 *   title: "Your Panel",
 *   position: "right",
 *   icon: <SomeIcon size={14} />,
 *   component: YourPanel,
 *   toolbarOrder: 40,
 * });
 * ```
 */

import type { ReactNode, ComponentType } from "react";

export interface PanelRegistration {
  /** Unique panel id — also used as the key in showPanel state. */
  id: string;
  /** Human-readable title shown in the flyout header and toolbar button. */
  title: string;
  /** Flyout attachment point. */
  position: "right" | "bottom";
  /** Icon element for the toolbar button and flyout header. */
  icon: ReactNode;
  /** The panel component to render inside the flyout. */
  component: ComponentType;
  /** Sort order for the toolbar. Lower = further left. */
  toolbarOrder: number;
  /** Extra CSS classes forwarded to FlyoutSurface className. */
  className?: string;
}

const _registry: Map<string, PanelRegistration> = new Map();

/**
 * Register a panel. Call this at module scope in your panel file.
 * Duplicate registrations (same id) are silently ignored after the first.
 */
export function registerPanel(panel: PanelRegistration): void {
  if (_registry.has(panel.id)) return;
  _registry.set(panel.id, panel);
}

/**
 * Returns all registered panels sorted by toolbarOrder ascending.
 */
export function getRegisteredPanels(): PanelRegistration[] {
  return Array.from(_registry.values()).sort((a, b) => a.toolbarOrder - b.toolbarOrder);
}

/**
 * Look up a single panel by id (returns undefined if not registered).
 */
export function getPanel(id: string): PanelRegistration | undefined {
  return _registry.get(id);
}
