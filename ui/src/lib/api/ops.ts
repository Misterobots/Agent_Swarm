import type { OpsHealth, TraceListResponse, TraceDetail } from "@/types/ops";

const API_BASE = "/api/backend";

export async function fetchOpsHealth(): Promise<OpsHealth | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ops/health`);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function fetchTraces(limit = 50): Promise<TraceListResponse> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ops/traces?limit=${limit}`);
    if (!response.ok) return { data: [], error: `HTTP ${response.status}` };
    return response.json();
  } catch (e) {
    return { data: [], error: String(e) };
  }
}

export async function fetchTraceDetail(traceId: string): Promise<TraceDetail | null> {
  try {
    const response = await fetch(
      `${API_BASE}/api/v1/ops/traces/${encodeURIComponent(traceId)}`
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}
