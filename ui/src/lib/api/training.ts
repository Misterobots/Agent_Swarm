import type { TrainingRun, ModelCatalog } from "@/types/ops";

const API_BASE = "/api/backend";

export async function fetchTrainingRuns(): Promise<TrainingRun[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/training/runs`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.runs ?? [];
  } catch {
    return [];
  }
}

export async function fetchModelCatalog(): Promise<ModelCatalog> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/training/catalog`);
    if (!response.ok) return { ollama_models: [], local_gguf: [], errors: [] };
    return response.json();
  } catch {
    return { ollama_models: [], local_gguf: [], errors: [] };
  }
}
