import type {
  BmoSandboxResponse,
  ComfyCheckpoints,
  ComfyStatus,
  EvidenceContent,
  EvidenceFile,
  GalleryItem,
  GovernanceCreatePayload,
  GovernanceRequest,
  MediaGenerationResult,
} from "@/types/workspaces";

const API_BASE = "/api/backend";
const SWARM_API_KEY = process.env.NEXT_PUBLIC_SWARM_API_KEY ?? "";

export async function fetchEvidenceFolders(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/v1/ops/evidence/folders`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.folders ?? [];
}

export async function fetchEvidenceFiles(folder: string): Promise<EvidenceFile[]> {
  const res = await fetch(`${API_BASE}/api/v1/ops/evidence/files?folder=${encodeURIComponent(folder)}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.files ?? [];
}

export async function fetchEvidenceContent(folder: string, filename: string): Promise<EvidenceContent | null> {
  const params = new URLSearchParams({ folder, filename });
  const res = await fetch(`${API_BASE}/api/v1/ops/evidence/content?${params.toString()}`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchGallery(kind: "all" | "image" | "audio" | "model"): Promise<GalleryItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/media/gallery?kind=${kind}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.items ?? [];
}

export async function fetchGovernanceRequests(): Promise<GovernanceRequest[]> {
  const res = await fetch(`${API_BASE}/api/v1/request`);
  if (!res.ok) return [];
  return res.json();
}

export async function updateGovernanceStatus(
  reqId: string,
  status: GovernanceRequest["status"],
  note?: string
): Promise<GovernanceRequest | null> {
  const res = await fetch(`${API_BASE}/api/v1/request/${encodeURIComponent(reqId)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note: note || null }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function createGovernanceRequest(
  payload: GovernanceCreatePayload
): Promise<GovernanceRequest | null> {
  const res = await fetch(`${API_BASE}/api/v1/request`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Swarm-Source": SWARM_API_KEY,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchComfyStatus(): Promise<ComfyStatus | null> {
  const res = await fetch(`${API_BASE}/api/v1/media/comfyui/status`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchComfyCheckpoints(): Promise<ComfyCheckpoints> {
  const res = await fetch(`${API_BASE}/api/v1/media/comfyui/checkpoints`);
  if (!res.ok) return { models: [] };
  return res.json();
}

export async function generateActionFigure(input: {
  prompt: string;
  model_name: string;
  cfg: number;
  steps: number;
  sampler: string;
  scheduler: string;
}): Promise<MediaGenerationResult | null> {
  const res = await fetch(`${API_BASE}/api/v1/media/generate/image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...input,
      prompt: `Action figure concept art, collectible toy, articulated joints, studio render, ${input.prompt}`,
      width: 1024,
      height: 1024,
      seed: -1,
    }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function generateCreatureForge(input: {
  image_path: string;
  workflow_name: string;
}): Promise<MediaGenerationResult | null> {
  const res = await fetch(`${API_BASE}/api/v1/media/generate/3d`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function synthesizeVoice(text: string, pitch: number, method: string): Promise<Blob | null> {
  const res = await fetch(`${API_BASE}/api/v1/training/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, pitch, method }),
  });
  if (!res.ok) return null;
  return res.blob();
}

export async function runBmoSandboxPrompt(text: string): Promise<BmoSandboxResponse | null> {
  const res = await fetch(`${API_BASE}/v1/voice/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) return null;
  return res.json();
}
