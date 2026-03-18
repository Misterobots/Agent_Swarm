"use client";

import { useEffect, useState } from "react";
import { fetchModels } from "@/lib/api/chat";
import type { Model } from "@/types/chat";

export function useModels() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchModels()
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setLoading(false));
  }, []);

  return { models, loading };
}
