import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ALL_FEATURE_KEYS, type FeatureKey } from "@/lib/onboarding/feature-registry";

/**
 * Tracks which feature callouts the current user has dismissed.
 *
 * `seenFeatures` is a monotonic, append-only set — keys are only ever added
 * (markSeen / markAllSeen), never removed. That makes cross-device sync a
 * plain set union with no last-write-wins races (see use-onboarding-sync.ts).
 *
 * localStorage (via persist) is the offline / first-paint cache; the backend
 * (hive_user_prefs) is the source of truth, reconciled on mount by hydrate().
 */
interface OnboardingState {
  /** Feature keys the user has dismissed. */
  seenFeatures: FeatureKey[];
  /** True once the server reconciliation on mount has completed. */
  hydrated: boolean;
  /** Which feature's first-use popover is currently open (only one at a time). */
  activePopover: FeatureKey | null;

  markSeen: (key: FeatureKey) => void;
  /** Mark several keys seen in one update (e.g. welcome + the modes it showcased). */
  markSeenMany: (keys: FeatureKey[]) => void;
  markAllSeen: () => void;
  hasSeen: (key: FeatureKey) => boolean;

  /** Union-merge server state into local. Called by useOnboardingSync on mount. */
  hydrate: (serverFeatures: FeatureKey[]) => void;

  setActivePopover: (key: FeatureKey | null) => void;
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      seenFeatures: [],
      hydrated: false,
      activePopover: null,

      markSeen: (key) =>
        set((s) => ({ seenFeatures: [...new Set([...s.seenFeatures, key])] })),

      markSeenMany: (keys) =>
        set((s) => ({ seenFeatures: [...new Set([...s.seenFeatures, ...keys])] })),

      markAllSeen: () =>
        set((s) => ({ seenFeatures: [...new Set([...s.seenFeatures, ...ALL_FEATURE_KEYS])] })),

      hasSeen: (key) => get().seenFeatures.includes(key),

      hydrate: (serverFeatures) =>
        set((s) => ({
          seenFeatures: [...new Set([...s.seenFeatures, ...serverFeatures])],
          hydrated: true,
        })),

      setActivePopover: (key) => set({ activePopover: key }),
    }),
    {
      name: "memex-onboarding",
      version: 1,
      // Only the seen set is durable. hydrated/activePopover are session-only —
      // persisting `hydrated: true` would skip server reconciliation on reload.
      partialize: (s) => ({ seenFeatures: s.seenFeatures }),
    }
  )
);
