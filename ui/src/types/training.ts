export interface TrainingRun {
  id: number;
  run_type: "export" | "synthetic" | "training" | "conversion";
  target_model: string | null;
  dataset_path?: string | null;
  dataset_size: number | null;
  status: "pending" | "running" | "completed" | "failed";
  metrics: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface ModelVersion {
  id: number;
  base_model: string;
  version_tag: string;
  ollama_model_name: string | null;
  status: "candidate" | "ab_testing" | "promoted" | "retired";
  avg_score: number;
  total_invocations: number;
  created_at: string;
}

export interface ActiveRun {
  run_id: number | null;
  status: string;
  started_at: string | null;
}

export interface TrainingStatus {
  last_run: TrainingRun | null;
  dataset_size: { exported: number; synthetic: number };
  active_ab_tests: number;
  model_versions: ModelVersion[];
  active_run?: ActiveRun | null;
}
