import type { TrainingStatus } from "@/types/training";

const API_BASE = "/api/backend";

export async function fetchTrainingStatus(): Promise<TrainingStatus> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    // Return empty status when endpoint isn't available yet
    return {
      last_run: null,
      dataset_size: { exported: 0, synthetic: 0 },
      active_ab_tests: 0,
      model_versions: [],
    };
  }
}
