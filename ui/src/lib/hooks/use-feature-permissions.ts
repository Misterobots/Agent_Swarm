"use client";

import { useEffect, useState } from "react";

export type FeaturePermissions = Record<string, boolean>;

interface PermissionResponse {
  features?: FeaturePermissions;
}

/**
 * Mirrors the backend feature policy so controls do not invite a request the
 * API will reject. The UI fails closed while this policy is unavailable; the
 * server remains the authoritative enforcement point for direct API callers.
 */
export function useFeaturePermissions() {
  const [features, setFeatures] = useState<FeaturePermissions>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/backend/api/v1/permissions")
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: PermissionResponse | null) => {
        if (!cancelled && payload?.features) {
          setFeatures((current) => ({ ...current, ...payload.features }));
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  return { features, loading, isAllowed: (feature: string) => !loading && features[feature] === true };
}
