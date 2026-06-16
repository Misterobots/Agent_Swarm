"use client";

/**
 * Per-feature callout state for a single feature key.
 *
 *   const { isNew, isPopoverOpen, meta, openPopover, dismiss } =
 *     useFeatureCallout("swarm_v1");
 *
 * `isNew` drives the badge dot; `isPopoverOpen` drives the first-use popover.
 * Both stay false until the store has hydrated from the server, so a feature
 * the user already dismissed on another device never flashes a callout.
 */

import { useEffect, useRef } from "react";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import {
  FEATURE_REGISTRY,
  SPOTLIGHT_FEATURE_KEYS,
  type FeatureKey,
} from "@/lib/onboarding/feature-registry";

export function useFeatureCallout(key: FeatureKey) {
  const hydrated = useOnboardingStore((s) => s.hydrated);
  const hasSeen = useOnboardingStore((s) => s.seenFeatures.includes(key));
  const activePopover = useOnboardingStore((s) => s.activePopover);
  const markSeen = useOnboardingStore((s) => s.markSeen);
  const setActivePopover = useOnboardingStore((s) => s.setActivePopover);

  const isNew = hydrated && !hasSeen;
  const isPopoverOpen = isNew && activePopover === key;

  return {
    /** Show the "New" badge dot on the anchor control. */
    isNew,
    /** This feature's popover is the active one. */
    isPopoverOpen,
    meta: FEATURE_REGISTRY[key],
    openPopover: () => setActivePopover(key),
    dismiss: () => {
      markSeen(key);
      if (useOnboardingStore.getState().activePopover === key) {
        setActivePopover(null);
      }
    },
  };
}

/**
 * True when the user has never dismissed the first-login welcome. Drives the
 * WelcomeCard in the chat empty state.
 */
export function useIsNewUser() {
  const hydrated = useOnboardingStore((s) => s.hydrated);
  const seenWelcome = useOnboardingStore((s) => s.seenFeatures.includes("welcome_v1"));
  return hydrated && !seenWelcome;
}

/**
 * Auto-opens a single spotlight popover for the first unseen spotlight feature,
 * once per session, for RETURNING users only. New users are covered by the
 * WelcomeCard (which marks the showcased modes seen), so they get no spotlight.
 *
 * Mount once on the chat page (near useOnboardingSync) — the spotlight features
 * are anchored to the always-mounted toolbar chips.
 */
export function useFeatureSpotlight() {
  const hydrated = useOnboardingStore((s) => s.hydrated);
  const seenFeatures = useOnboardingStore((s) => s.seenFeatures);
  const activePopover = useOnboardingStore((s) => s.activePopover);
  const setActivePopover = useOnboardingStore((s) => s.setActivePopover);
  const firedRef = useRef(false);

  useEffect(() => {
    if (firedRef.current || !hydrated) return;
    // New users: the welcome handles onboarding — no spotlight.
    if (!seenFeatures.includes("welcome_v1")) return;
    // Don't stack on top of an already-open popover.
    if (activePopover) return;

    const next = SPOTLIGHT_FEATURE_KEYS.find((k) => !seenFeatures.includes(k));
    firedRef.current = true; // fire at most once per session, found or not
    if (next) setActivePopover(next);
  }, [hydrated, seenFeatures, activePopover, setActivePopover]);
}
