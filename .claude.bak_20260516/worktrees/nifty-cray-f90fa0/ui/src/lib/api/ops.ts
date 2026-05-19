import type { OpsHealth, TraceListResponse, TraceDetail, Observation, ServiceCheckResponse } from "@/types/ops";

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

export async function fetchObservations(
  traceId: string
): Promise<Observation[]> {
  try {
    const response = await fetch(
      `${API_BASE}/api/v1/ops/traces/${encodeURIComponent(traceId)}/observations?limit=50`
    );
    if (!response.ok) return [];
    const data = await response.json();
    return data.observations || [];
  } catch {
    return [];
  }
}

export async function fetchServiceChecks(): Promise<ServiceCheckResponse> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ops/services`);
    if (!response.ok) return { services: [], summary: { total: 0, healthy: 0, unhealthy: 0 } };
    return response.json();
  } catch {
    return { services: [], summary: { total: 0, healthy: 0, unhealthy: 0 } };
  }
}

export async function restartService(serviceId: string): Promise<{ status: string; detail?: string }> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ops/services/${encodeURIComponent(serviceId)}/restart`, {
      method: "POST",
    });
    const data = await response.json();
    if (!response.ok) return { status: "error", detail: data.detail || `HTTP ${response.status}` };
    return { status: "restarted" };
  } catch (e) {
    return { status: "error", detail: String(e) };
  }
}