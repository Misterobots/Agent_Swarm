import { Network, Search, Hammer, Palette, Users } from "lucide-react";
import type { ComponentType } from "react";

/**
 * Versioned feature-callout keys. Append a new key (e.g. "swarm_v2") when a
 * feature changes enough to warrant re-announcing it — old keys stay so users
 * who saw v1 aren't re-prompted for unrelated features.
 *
 * `welcome_v1` is the first-login welcome; it has no badge anchor and renders
 * only in the chat empty state.
 */
export type FeatureKey =
  | "welcome_v1"
  | "swarm_v1"
  | "research_v1"
  | "workshop_v1"
  | "design_v1"
  | "pioneer_academy_v1";

export interface FeatureMeta {
  key: FeatureKey;
  title: string;
  /** One- or two-sentence pitch shown in the popover / welcome card. */
  description: string;
  icon: ComponentType<{ size?: number; className?: string }>;
  /**
   * Prefilled into the chat input when the user clicks "Try it" in the
   * popover. Omit for features that aren't a single prompt (e.g. welcome).
   */
  tryItPrompt?: string;
  /**
   * Whether this feature surfaces a "New" badge dot on an anchor control.
   * Welcome is empty-state only, so it has no badge.
   */
  badge: boolean;
  /**
   * Whether a returning user gets an auto-opening spotlight popover for this
   * feature on login. Only set for features whose anchor is always mounted on
   * the chat page (the toolbar chips) — settings-menu/contextual anchors aren't
   * mounted on load, so they stay dot/contextual only.
   */
  spotlight?: boolean;
  /** Human-readable note on where the badge anchors (docs for implementers). */
  anchor?: string;
}

export const FEATURE_REGISTRY: Record<FeatureKey, FeatureMeta> = {
  welcome_v1: {
    key: "welcome_v1",
    title: "Welcome to Memex",
    description:
      "Your local AI workspace. Chat with the swarm, research the web, run multi-agent builds, and design UIs — all from one place.",
    icon: Network,
    badge: false,
  },
  swarm_v1: {
    key: "swarm_v1",
    title: "Swarm mode",
    description:
      "Route a task through the multi-agent coordinator. A team of specialist agents plans, builds, and verifies the work together.",
    icon: Network,
    tryItPrompt: "Build me a small CLI todo app in Python with tests",
    badge: true,
    spotlight: true,
    anchor: "InputToolbar 'Swarm' chip",
  },
  research_v1: {
    key: "research_v1",
    title: "Research mode",
    description:
      "Deep web and document research. The agent gathers sources, cross-checks them, and synthesizes a grounded answer.",
    icon: Search,
    tryItPrompt: "Research the current state of local-first sync engines",
    badge: true,
    spotlight: true,
    anchor: "InputToolbar 'Research' chip",
  },
  workshop_v1: {
    key: "workshop_v1",
    title: "Workshop mode",
    description:
      "Turn a rough idea into a product brief. Workshop asks sharp questions, then hands off to Design and Swarm to build it.",
    icon: Hammer,
    tryItPrompt: "/workshop a habit-tracking app for families",
    badge: true,
    anchor: "ChatSettingsMenu 'Workshop' toggle",
  },
  design_v1: {
    key: "design_v1",
    title: "Design mode",
    description:
      "Generate a self-contained UI mockup you can preview and open in the studio — no build step required.",
    icon: Palette,
    tryItPrompt: "/design a clean dashboard for a home energy monitor",
    badge: true,
    anchor: "ChatSettingsMenu 'Design' toggle",
  },
  pioneer_academy_v1: {
    key: "pioneer_academy_v1",
    title: "Meet the pioneers",
    description:
      "Each swarm worker is a computing pioneer with their own portrait and specialty. Watch them collaborate live on the swarm panel.",
    icon: Users,
    badge: true,
    anchor: "Swarm drawer (first completed run)",
  },
};

export const ALL_FEATURE_KEYS = Object.keys(FEATURE_REGISTRY) as FeatureKey[];

/**
 * Features eligible for an auto-opening spotlight popover, in priority order.
 * Restricted to always-mounted anchors (the toolbar chips) so the popover
 * always has something to anchor to on login.
 */
export const SPOTLIGHT_FEATURE_KEYS = ALL_FEATURE_KEYS.filter(
  (k) => FEATURE_REGISTRY[k].spotlight
);
