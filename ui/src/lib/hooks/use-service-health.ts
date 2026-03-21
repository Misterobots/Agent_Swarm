"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchServiceHealth } from "@/lib/api/ops";
import type { HealthResponse } from "@/types/ops";

export function useServiceHealth(intervalMs = 30000) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchServiceHealth();
      if (data) {
        setHealth(data);
        setError(null);
      } else {
        setError("Failed to fetch health data");
      }
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, intervalMs);
    return () => clearInterval(interval);
  }, [refresh, intervalMs]);

  return { health, loading, error, refresh };
}
