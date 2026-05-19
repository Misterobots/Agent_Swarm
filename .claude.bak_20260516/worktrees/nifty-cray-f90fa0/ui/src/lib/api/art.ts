const API_BASE = "/api/backend";

// ── Job polling infrastructure ─────────────────────────────────────────────

interface ArtJobResponse {
  status: string;
  result: string | null;
  mode: string;
  prompt: string;
  created_at: string;
  finished_at: string | null;
}

interface SubmitResponse {
  job_id: string;
  status: string;
}

/**
 * Poll a generation job until it finishes.
 * Returns the final {status, result} matching the old synchronous contract.
 * Calls onProgress with intermediate status messages for UI feedback.
 */
async function pollJob(
  jobId: string,
  onProgress?: (msg: string) => void,
  intervalMs = 3000,
  maxWaitMs = 1800_000, // 30 min
): Promise<{ status: string; result: string }> {
  const deadline = Date.now() + maxWaitMs;

  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${API_BASE}/v1/art/jobs/${jobId}`);
      if (!res.ok) {
        return { status: "error", result: `Job poll failed (${res.status})` };
      }
      const job: ArtJobResponse = await res.json();

      if (job.status === "running") {
        if (job.result && onProgress) onProgress(job.result);
        await new Promise((r) => setTimeout(r, intervalMs));
        continue;
      }

      // Terminal state: ok or error
      return { status: job.status, result: job.result ?? "No result" };
    } catch (err) {
      // Network blip — retry
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }

  return { status: "error", result: "Generation timed out waiting for result." };
}

async function safeSubmit(url: string, body: object): Promise<SubmitResponse> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { job_id: "", status: "error" } as SubmitResponse & { result?: string };
  }
}

// ── Public API ──────────────────────────────────────────────────────────────

export async function fetchArtModels(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/v1/art/models`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.models || [];
}

export interface ImageGenParams {
  prompt: string;
  model_name: string;
  cfg: number;
  steps: number;
  width: number;
  height: number;
  sampler: string;
  scheduler: string;
  seed: number;
}

export async function generateImage(
  params: ImageGenParams,
  onProgress?: (msg: string) => void,
) {
  const sub = await safeSubmit(`${API_BASE}/v1/art/generate/image`, params);
  if (!sub.job_id) return { status: "error", result: "Failed to submit job" };
  return pollJob(sub.job_id, onProgress);
}

export interface ThreeDGenParams {
  prompt: string;
  workflow: string;
  auto_concept: boolean;
  quality?: string;
  steps?: number;
  cfg?: number;
}

export async function generate3D(
  params: ThreeDGenParams,
  onProgress?: (msg: string) => void,
) {
  const sub = await safeSubmit(`${API_BASE}/v1/art/generate/3d`, params);
  if (!sub.job_id) return { status: "error", result: "Failed to submit job" };
  return pollJob(sub.job_id, onProgress);
}

export interface ActionFigureParams {
  prompt: string;
  workflow: string;
  target_height: number;
  clearance: number;
}

export async function generateActionFigure(
  params: ActionFigureParams,
  onProgress?: (msg: string) => void,
) {
  const sub = await safeSubmit(`${API_BASE}/v1/art/generate/action-figure`, params);
  if (!sub.job_id) return { status: "error", result: "Failed to submit job" };
  return pollJob(sub.job_id, onProgress);
}

export interface GalleryImage {
  filename: string;
  url: string;
  size_bytes: number;
  meta: Record<string, unknown>;
}

export async function fetchImageGallery(): Promise<GalleryImage[]> {
  const res = await fetch(`${API_BASE}/v1/art/gallery/images`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.images || [];
}

export interface Gallery3DFile {
  filename: string;
  category: string;
  ext: string;
  size_bytes: number;
  url: string;
  download_url: string;
  path?: string;
}

export async function fetch3DGallery(): Promise<Gallery3DFile[]> {
  const res = await fetch(`${API_BASE}/v1/art/gallery/3d`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.files || [];
}

// ── Mesh file URL (for Three.js viewer) ──────────────────────────────────

/**
 * Convert a backend mesh path to a browser-fetchable URL.
 * e.g. "/app/comfy_io/output/3D/TripoSG_00001.glb" → "/api/backend/v1/art/files/3D/TripoSG_00001.glb"
 */
export function meshFileUrl(backendPath: string): string {
  const relative = backendPath.replace(/^\/app\/comfy_io\/output\//, "");
  return `${API_BASE}/v1/art/files/${relative}`;
}

// ── Smooth mesh for printing ─────────────────────────────────────────────

export async function smoothMesh(
  meshPath: string,
  targetHeight = 150,
  smoothIterations = 10,
): Promise<{ status: string; path?: string }> {
  const res = await fetch(`${API_BASE}/v1/art/smooth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mesh_path: meshPath,
      target_height: targetHeight,
      smooth_iterations: smoothIterations,
    }),
  });
  return res.json();
}

// ── Segment mesh at user-placed joints ───────────────────────────────────

export interface JointPositionInput {
  x: number;
  y: number;
  z: number;
}

export async function segmentWithJoints(
  params: {
    mesh_path: string;
    joints: Record<string, JointPositionInput>;
    target_height: number;
    clearance: number;
  },
  onProgress?: (msg: string) => void,
) {
  const sub = await safeSubmit(`${API_BASE}/v1/art/segment`, params);
  if (!sub.job_id) return { status: "error", result: "Failed to submit segmentation job" };
  return pollJob(sub.job_id, onProgress);
}
