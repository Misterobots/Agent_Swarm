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

export interface ServiceCheck {
  id: string;
  name: string;
  node: string;
  ip: string;
  port: number;
  container: string;
  healthy: boolean;
  latency_ms: number | null;
  detail: string;
}

export interface ServiceCheckResponse {
  services: ServiceCheck[];
  summary: { total: number; healthy: number; unhealthy: number };
}

// NR ops types (used by monitoring components)
export interface ServiceStatus {
  name: string;
  status: "healthy" | "down" | "unreachable";
  port: number;
  latency?: number;
}

export interface HealthResponse {
  nodes: import("./chat").NodeHealth[];
  controlPlane: ServiceStatus[];
  containers: ContainerInfo[];
  timestamp: number;
}

export interface ContainerInfo {
  name: string;
  status: string;
  image: string;
  uptime: string;
}

export interface LangfuseTrace {
  id: string;
  name: string;
  timestamp: string;
  input: string;
  latency: number | null;
  status: "SUCCESS" | "ERROR";
}

export interface LangfuseTraceDetail {
  id: string;
  name: string;
  timestamp: string;
  latency: number | null;
  level: string;
  input: unknown;
  output: unknown;
  metadata: unknown;
}

export interface LangfuseObservation {
  id: string;
  type: string;
  name: string;
  level: string;
  startTime: string;
  endTime: string;
  model?: string;
  usage?: { input?: number; output?: number; totalCost?: number };
  input: unknown;
  output: unknown;
  metadata: unknown;
}
