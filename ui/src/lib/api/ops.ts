import type {
  HealthResponse,
  LangfuseTrace,
  LangfuseTraceDetail,
  LangfuseObservation,
} from "@/types/ops";

export async function fetchServiceHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch("/api/services/health");
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchTraces(
  limit = 50,
  search?: string
): Promise<LangfuseTrace[]> {
  try {
    const params = new URLSearchParams({ limit: String(limit), orderBy: "timestamp.desc" });
    const res = await fetch(`/api/langfuse/traces?${params}`);
    if (!res.ok) return [];
    const data = await res.json();
    const traces: LangfuseTrace[] = (data.data || []).map(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (t: any) => ({
        id: t.id,
        name: t.name || "unknown",
        timestamp: t.timestamp,
        input: typeof t.input === "string" ? t.input.slice(0, 80) : JSON.stringify(t.input ?? "").slice(0, 80),
        latency: t.latency ?? null,
        status: t.level === "ERROR" ? "ERROR" : "SUCCESS",
      })
    );
    if (search) {
      const q = search.toLowerCase();
      return traces.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.input.toLowerCase().includes(q) ||
          t.id.includes(q)
      );
    }
    return traces;
  } catch {
    return [];
  }
}

export async function fetchTraceDetail(
  traceId: string
): Promise<LangfuseTraceDetail | null> {
  try {
    const res = await fetch(`/api/langfuse/traces/${traceId}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchObservations(
  traceId: string
): Promise<LangfuseObservation[]> {
  try {
    const res = await fetch(
      `/api/langfuse/observations?traceId=${traceId}&limit=50`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return data.data || [];
  } catch {
    return [];
  }
}
