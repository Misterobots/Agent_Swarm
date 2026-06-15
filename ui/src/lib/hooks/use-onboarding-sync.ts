"use client";

/**
 * Cross-device onboarding sync.
 *
 * Mirrors use-conversation-sync.ts:
 *  - On mount, hydrate from the backend (union with the persisted local cache).
 *  - On every change after hydration, write the seen set back (fire-and-forget).
 *
 * seenFeatures is a monotonic set, so the backend unions server-side too — a
 * stale client can never shrink another device's state. localStorage holds the
 * set offline; it resyncs on the next successful mount.
 *
 * Mount this once, near useConversationSync() in chat-view.tsx.
 */

import { useEffect, useRef } from "react";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import type { FeatureKey } from "@/lib/onboarding/feature-registry";

const API = "/api/backend/v1/prefs/onboarding";

export function useOnboardingSync() {
  const hydrate = useOnboardingStore((s) => s.hydrate);
  const seenFeatures = useOnboardingStore((s) => s.seenFeatures);
  const hydrated = useOnboardingStore((s) => s.hydrated);

  // Step 1: hydrate from server on mount (union with persisted local cache).
  useEffect(() => {
    let mounted = true;
    fetch(API)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { seenFeatures?: FeatureKey[] } | null) => {
        if (!mounted) return;
        if (data?.seenFeatures) hydrate(data.seenFeatures);
        else useOnboardingStore.setState({ hydrated: true });
      })
      .catch(() => {
        // Offline — fall back to the persisted local cache.
        if (mounted) useOnboardingStore.setState({ hydrated: true });
      });
    return () => {
      mounted = false;
    };
  }, [hydrate]);

  // Step 2: write-back on change, but only after hydration. The `hydrated`
  // guard stops the initial empty array from clobbering server state on first
  // paint (the server-side union makes a stray [] a no-op anyway).
  const lastSent = useRef<string>("");
  useEffect(() => {
    if (!hydrated) return;
    const payload = JSON.stringify({ seenFeatures });
    if (payload === lastSent.current) return;
    lastSent.current = payload;
    fetch(API, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: payload,
    }).catch(() => {
      // Offline — local cache keeps it; resyncs next mount. Allow a retry.
      lastSent.current = "";
    });
  }, [seenFeatures, hydrated]);
}
