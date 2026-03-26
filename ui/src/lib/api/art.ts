const API_BASE = "/api/backend";

export async function fetchArtModels(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/v1/art/models`);
  if (!res.ok) return ["v1-5-pruned-emaonly.ckpt"];
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

export async function generateImage(params: ImageGenParams) {
  const res = await fetch(`${API_BASE}/v1/art/generate/image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json();
}

export interface ThreeDGenParams {
  prompt: string;
  workflow: string;
  auto_concept: boolean;
}

export async function generate3D(params: ThreeDGenParams) {
  const res = await fetch(`${API_BASE}/v1/art/generate/3d`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json();
}

export interface ActionFigureParams {
  prompt: string;
  workflow: string;
  target_height: number;
  clearance: number;
}

export async function generateActionFigure(params: ActionFigureParams) {
  const res = await fetch(`${API_BASE}/v1/art/generate/action-figure`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json();
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
  path: string;
}

export async function fetch3DGallery(): Promise<Gallery3DFile[]> {
  const res = await fetch(`${API_BASE}/v1/art/gallery/3d`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.files || [];
}
