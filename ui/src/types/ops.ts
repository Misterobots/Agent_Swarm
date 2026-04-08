export interface Container {
  name: string;
  image: string;
  uptime: string;
  status: string;
}

export interface ClusterNode {
  name: string;
  role: "execution" | "gateway" | "control";
  ip: string;
  healthy: boolean;
  running_count: number;
  containers: Container[];
  error?: string | null;
}

export interface ControlPlaneService {
  name: string;
  port: number;
  healthy: boolean;
}

export interface OpsHealth {
  status: string;
  running_count: number;
  nodes: ClusterNode[];
  execution_plane: Container[];
  control_plane: ControlPlaneService[];
}

export interface Trace {
  id: string;
  timestamp: string | null;
  name: string;
  input_preview: string;
  latency: number | null;
  level: string;
}

export interface TraceListResponse {
  data: Trace[];
  error?: string;
}

export interface Observation {
  id: string;
  type: string;
  name: string;
  level: string;
  startTime?: string;
  endTime?: string;
  model?: string;
  input?: unknown;
  output?: unknown;
  usage?: {
    input?: number;
    output?: number;
    totalCost?: number;
  };
  metadata?: unknown;
}

export interface TraceDetail {
  trace: Record<string, unknown>;
  observations: Observation[];
  langfuse_url: string;
}

export interface TrainingRun {
  id: string;
  base_model: string;
  started_at?: string;
  num_epochs?: number;
  status: "in_progress" | "complete" | "converted";
  adapter_ready: boolean;
  gguf_files: string[];
}

export interface OllamaModel {
  name: string;
  size_mb: number;
  modified_at?: string;
  node: string;
  digest: string;
}

export interface LocalGGUF {
  name: string;
  path: string;
  size_mb: number;
  run_id: string;
}

export interface ModelCatalog {
  ollama_models: OllamaModel[];
  local_gguf: LocalGGUF[];
  errors: string[];
}
