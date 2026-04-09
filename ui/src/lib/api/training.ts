import type { TrainingStatus, TrainingRun } from "@/types/training";
import type { ModelCatalog, TrainingRun as OpsTrainingRun } from "@/types/ops";

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
  template_id?: string | null;
}

export interface CuratedDataset {
  key: string;
  hf_id: string;
  description: string;
  category: string;
  default_max: number;
  recommended_for: string[];
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

export interface TrainingReport {
  run_id: number;
  status: string;
  run_type: string;
  timing: {
    started_at: string | null;
    completed_at: string | null;
    total_wall_clock_sec: number | null;
    active_training_sec: number | null;
    overhead_sec: number | null;
    overhead_note: string;
  };
  dataset: {
    path: string | null;
    total_samples: number | null;
    training_examples: number | null;
  };
  model: {
    base_model: string | null;
    trainable_params: number | null;
    total_params: number | null;
    trainable_pct: number | null;
  };
  hyperparameters: Record<string, unknown>;
  results: {
    final_loss: number | null;
    train_samples_per_second: number | null;
    train_steps_per_second: number | null;
    adapter_path: string | null;
  };
  deployment: {
    model_version: {
      id: number;
      version_tag: string;
      ollama_model_name: string | null;
      status: string;
      avg_score: number;
      total_invocations: number;
    } | null;
    ab_test: {
      id: number;
      candidate_model: string;
      base_model: string;
      status: string;
      winner: string | null;
      result_count: number;
      candidate_avg_score: number | null;
      base_avg_score: number | null;
    } | null;
  };
  error: string | null;
}

export async function fetchTrainingReport(runId: number): Promise<TrainingReport | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/runs/${runId}/report`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
//  Convert & Deploy types + API functions
// ---------------------------------------------------------------------------

export interface ConvertReport {
  source_run_id: number;
  conversion_run_id: number;
  status: string;
  method: string | null;
  timing: {
    total_sec: number | null;
    merge_sec: number | null;
    convert_sec: number | null;
    ollama_import_sec: number | null;
  };
  ollama: {
    model_name: string | null;
    verified: boolean | null;
  };
  model_version: {
    id: number;
    version_tag: string;
    ollama_model_name: string | null;
    status: string;
    avg_score: number;
    total_invocations: number;
  } | null;
  warnings: string[];
  error: string | null;
}

export interface DeployReport {
  source_run_id: number;
  status: string;
  model_version: {
    id: number;
    ollama_model_name: string | null;
    version_tag: string;
    status: string;
  };
  test: {
    id: number;
    template_id: string;
    candidate_model: string;
    base_model: string;
    traffic_split: number | null;
    min_invocations: number;
    status: string;
    winner: string | null;
    started_at: string | null;
    concluded_at: string | null;
  } | null;
  results?: {
    n_candidate: number;
    n_base: number;
    total_samples: number;
    candidate_avg_score: number | null;
    base_avg_score: number | null;
    improvement_pct: number | null;
    p_value: number | null;
  };
  evaluation?: Record<string, unknown> | null;
}

export interface Template {
  id: string;
  intent: string;
  default_model: string;
}

export async function startConvert(req: {
  training_run_id: number;
  base_model?: string | null;
  system_prompt?: string | null;
}): Promise<{ status: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/convert`, {
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

export async function startDeploy(req: {
  training_run_id: number;
  template_id: string;
  traffic_split?: number;
  min_invocations?: number;
}): Promise<DeployReport | { status: string; error: string }> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/deploy`, {
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

export async function fetchConvertReport(runId: number): Promise<ConvertReport | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/runs/${runId}/convert-report`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDeployReport(runId: number): Promise<DeployReport | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/training/runs/${runId}/deploy-report`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchTemplates(): Promise<Template[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/templates`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.templates ?? [];
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

export async function fetchOpsTrainingRuns(): Promise<OpsTrainingRun[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/training/runs`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.runs ?? [];
  } catch {
    return [];
  }
}
