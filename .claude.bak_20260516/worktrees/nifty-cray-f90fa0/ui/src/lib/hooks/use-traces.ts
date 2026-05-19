"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchTraces } from "@/lib/api/ops";
import type { Trace } from "@/types/ops";

export function useTraces(limit = 50) {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchTraces(limit);
      let data = result.data;
      if (search) {
        const q = search.toLowerCase();
        data = data.filter(
          (t) =>
            t.name.toLowerCase().includes(q) ||
            t.input_preview.toLowerCase().includes(q) ||
            t.id.includes(q)
        );
      }
      setTraces(data);
      setError(result.error ?? null);
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
