import type { TrainingStatus, TrainingRun } from "@/types/training";

const API_BASE = "/api/backend";

export async function fetchTrainingStatus(): Promise<TrainingStatus> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return {
      last_run: null,
      dataset_size: { exported: 0, synthetic: 0, curated: 0 },
      active_ab_tests: 0,
      model_versions: [],
    };
  }
}

export async function fetchTrainingRuns(
  limit: number = 50
): Promise<TrainingRun[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/runs?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.runs ?? [];
  } catch {
    return [];
  }
}

export interface StartTrainingRequest {
  run_type: "training" | "export" | "full_pipeline" | "curated" | "synthetic";
  time_budget_minutes?: number | null;
  base_model?: string | null;
  lora_rank?: number | null;
  learning_rate?: number | null;
  epochs?: number | null;
  curated_datasets?: string[] | null;
  max_samples?: number | null;
  synthetic_target?: number | null;
}

export interface CuratedDataset {
  key: string;
  hf_id: string;
  description: string;
  category: string;
  default_max: number;
}

export async function fetchCuratedDatasets(): Promise<CuratedDataset[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/curated-datasets`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.datasets ?? [];
  } catch {
    return [];
  }
}

export async function startTraining(
  req: StartTrainingRequest
): Promise<{ status: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return { status: "error", error: body.detail ?? `HTTP ${res.status}` };
    }
    return await res.json();
  } catch (e) {
    return { status: "error", error: String(e) };
  }
}
