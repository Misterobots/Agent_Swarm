import type { ChatMessage, Model, NodeHealth } from "@/types/chat";
import { streamSSE } from "@/lib/utils/sse-parser";

const API_BASE = "/api/backend";

export async function* sendChatStream(
  messages: Pick<ChatMessage, "role" | "content">[],
  model: string = "swarm-standard",
  signal?: AbortSignal,
  sessionId?: string,
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, stream: true, session_id: sessionId }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status} ${response.statusText}`);
  }

  yield* streamSSE(response);
}

export async function fetchModels(): Promise<Model[]> {
  const response = await fetch(`${API_BASE}/v1/models`);
  if (!response.ok) return [];
  const data = await response.json();
  return data.data || [];
}

export async function fetchNodeHealth(): Promise<NodeHealth[]> {
  const response = await fetch(`${API_BASE}/api/v1/health/nodes`);
  if (!response.ok) return [];
  const data = await response.json();
  return data.nodes || [];
}
