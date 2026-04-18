export interface TrainingRun {
  id: number;
  run_type: "export" | "synthetic" | "training" | "conversion" | "curated" | "full_pipeline";
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
  run_type?: string;
  target_model?: string | null;
  dataset_size?: number | null;
}

export interface TrainingStatus {
  last_run: TrainingRun | null;
  dataset_size: { exported: number; synthetic: number; curated?: number };
  active_ab_tests: number;
  model_versions: ModelVersion[];
  active_run?: ActiveRun | null;
}

export interface LiveTrainingMetrics {
  run_id: number;
  status: string;
  phase: string | null;
  current_step: number;
  total_steps: number;
  current_epoch: number;
  total_epochs: number | null;
  loss: number | null;
  grad_norm: number | null;
  learning_rate: number | null;
  reward_mean: number | null;
  reward_std: number | null;
  entropy: number | null;
  step_time_sec: number | null;
  elapsed_sec: number | null;
  eta_sec: number | null;
  time_budget_sec: number | null;
  budget_remaining_sec: number | null;
  target_model: string | null;
  dataset_size: number | null;
  dataset_path: string | null;
}
