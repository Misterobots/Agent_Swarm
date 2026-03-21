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
