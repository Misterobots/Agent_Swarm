export interface EvidenceFile {
  name: string;
  size: number;
}

export interface EvidenceContent {
  name: string;
  folder: string;
  content: string;
  content_type: string;
}

export interface GalleryItem {
  name: string;
  kind: "image" | "audio" | "model";
  size_mb: number;
  updated_at: number;
  url: string;
  metadata?: Record<string, unknown> | null;
}

export interface GovernanceRequest {
  id: string;
  type: "PACKAGE" | "MODEL" | "PERMISSION" | "FEATURE" | "OTHER";
  description: string;
  user: string;
  timestamp: string;
  status: "PENDING" | "ASSESSING" | "APPROVED" | "REJECTED" | "COMPLETED" | "FAILED";
  assessment_notes: string[];
  admin_notes?: string | null;
}

export interface GovernanceCreatePayload {
  type: GovernanceRequest["type"];
  description: string;
  user: string;
}

export interface ComfyStatus {
  healthy: boolean;
  host: string;
  error?: string;
}

export interface ComfyCheckpoints {
  models: string[];
}

export interface MediaGenerationResult {
  result: string;
}
