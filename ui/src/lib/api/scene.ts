// Scene Composer API client.
// Talks to the /v1/art/scene/* endpoints added in agents/main.py for the
// complex-scene decomposition + OmniGen2 composite workflow.

const API_BASE = "/api/backend";

export type CardStatus = "pending" | "generating" | "ready" | "approved" | "rejected" | "error";
export type SceneState =
  | "decomposing"
  | "generating"
  | "awaiting_compose"
  | "composing"
  | "done"
  | "error";

export interface SceneCard {
  card_id: string;
  role: "establishing_shot" | "character" | "style";
  name: string;
  prompt: string;
  status: CardStatus;
  image_path: string | null;
  child_job_id: string | null;
  seed: number;
  error?: string;
}

export interface SceneJob {
  job_id: string;
  status: "running" | "ok" | "error";
  result: string | null;
  mode: "scene";
  prompt: string;
  state: SceneState;
  engine: "omnigen" | "flux-inpaint";
  cards: SceneCard[];
  composite_path?: string;
  created_at: string;
  finished_at: string | null;
}

interface SubmitResponse {
  job_id: string;
  status: string;
}

async function postJson<T>(url: string, body?: object): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function startScene(
  prompt: string,
  engine: "omnigen" | "flux-inpaint" = "omnigen",
): Promise<SubmitResponse> {
  return postJson(`${API_BASE}/v1/art/scene/start`, { prompt, engine });
}

export async function getScene(jobId: string): Promise<SceneJob> {
  const res = await fetch(`${API_BASE}/v1/art/scene/${jobId}`);
  if (!res.ok) throw new Error(`getScene ${res.status}`);
  return res.json();
}

export async function regenerateCard(jobId: string, cardId: string) {
  return postJson(`${API_BASE}/v1/art/scene/${jobId}/regenerate/${cardId}`);
}

export async function approveCard(jobId: string, cardId: string) {
  return postJson<{ card_id: string; status: "approved"; all_approved: boolean }>(
    `${API_BASE}/v1/art/scene/${jobId}/approve/${cardId}`,
  );
}

export async function composeScene(jobId: string): Promise<SubmitResponse> {
  return postJson(`${API_BASE}/v1/art/scene/${jobId}/compose`);
}

/** Poll a scene job and invoke onUpdate with each fresh snapshot. */
export async function pollScene(
  jobId: string,
  onUpdate: (job: SceneJob) => void,
  intervalMs = 2000,
  maxWaitMs = 1_800_000,
): Promise<SceneJob> {
  const deadline = Date.now() + maxWaitMs;
  let last: SceneJob | null = null;
  while (Date.now() < deadline) {
    try {
      const job = await getScene(jobId);
      onUpdate(job);
      last = job;
      // Stop polling on terminal states unless the user might still act
      // (awaiting_compose stays in the loop because the UI may approve more).
      if (job.state === "done" || job.status === "error") return job;
    } catch (err) {
      // Network blip — keep going
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  if (last) return last;
  throw new Error("Scene poll timed out");
}

export function galleryImageUrl(filename: string): string {
  return `${API_BASE}/v1/art/gallery/images/${filename}`;
}
