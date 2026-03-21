"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchTraces } from "@/lib/api/ops";
import type { LangfuseTrace } from "@/types/ops";

export function useTraces(limit = 50) {
  const [traces, setTraces] = useState<LangfuseTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTraces(limit, search || undefined);
      setTraces(data);
      setError(null);
    } catch {
      setError("Failed to fetch traces");
    } finally {
      setLoading(false);
    }
  }, [limit, search]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { traces, loading, error, search, setSearch, refresh };
}
