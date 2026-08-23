export type TriggerType = "cron" | "interval" | "once";
export type TriggerState = "active" | "paused" | "fired" | "failed";

export interface Trigger {
  trigger_id: string;
  name: string;
  trigger_type: TriggerType;
  state: TriggerState;
  fire_count: number;
  last_fired?: number | null;
  last_error?: string | null;
  task_config?: { prompt: string; swarm_mode?: boolean };
  cron?: { hour: number | null; minute: number | null; day_of_week: number | null };
  interval_seconds?: number;
  fire_at?: number;
}

export interface CreateTriggerBody {
  name: string;
  trigger_type: TriggerType;
  task_config: { prompt: string; swarm_mode?: boolean };
  cron?: { hour?: number; minute?: number; day_of_week?: number };
  interval_seconds?: number;
  delay_seconds?: number;
}

const BASE = "/api/backend/api/v1/trigger";

export async function listTriggers(): Promise<{ triggers: Trigger[]; status: number }> {
  try {
    const response = await fetch(`${BASE}/list`, { signal: AbortSignal.timeout(8000) });
    if (!response.ok) return { triggers: [], status: response.status };
    const data = await response.json();
    return { triggers: Array.isArray(data?.triggers) ? data.triggers : [], status: response.status };
  } catch {
    return { triggers: [], status: 0 };
  }
}

export async function createTrigger(body: CreateTriggerBody) {
  try {
    const response = await fetch(`${BASE}/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return { status: response.status };
    const data = await response.json();
    return { trigger: data?.trigger as Trigger | undefined, status: response.status };
  } catch {
    return { status: 0 };
  }
}

async function mutateTrigger(id: string, action: "pause" | "resume" | "delete") {
  try {
    const suffix = action === "delete" ? "" : `/${action}`;
    const response = await fetch(`${BASE}/${encodeURIComponent(id)}${suffix}`, {
      method: action === "delete" ? "DELETE" : "POST",
    });
    return response.ok;
  } catch {
    return false;
  }
}

export const pauseTrigger = (id: string) => mutateTrigger(id, "pause");
export const resumeTrigger = (id: string) => mutateTrigger(id, "resume");
export const deleteTrigger = (id: string) => mutateTrigger(id, "delete");
