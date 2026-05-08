import type {
  AckRequest,
  MaintenanceAuditRow,
  MaintenanceQueueItem,
  MaintenanceQueueStatus,
} from "@/types/maintenance";

const API_BASE = "/api/maintenance";

export async function fetchMaintenanceQueue(
  status: MaintenanceQueueStatus | "all" = "pending",
  limit = 200
): Promise<MaintenanceQueueItem[]> {
  try {
    const qs = new URLSearchParams({ status, limit: String(limit) });
    const res = await fetch(`${API_BASE}/api/maintenance/queue?${qs}`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { items?: MaintenanceQueueItem[] };
    return data.items ?? [];
  } catch {
    return [];
  }
}

export async function ackMaintenanceItem(
  id: number,
  body: AckRequest
): Promise<MaintenanceQueueItem | null> {
  try {
    const res = await fetch(`${API_BASE}/api/maintenance/queue/${id}/ack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return (await res.json()) as MaintenanceQueueItem;
  } catch {
    return null;
  }
}

export async function fetchMaintenanceAudit(
  limit = 100
): Promise<MaintenanceAuditRow[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/maintenance/audit?limit=${limit}`,
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    const data = (await res.json()) as { rows?: MaintenanceAuditRow[] };
    return data.rows ?? [];
  } catch {
    return [];
  }
}
