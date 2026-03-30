import type { ChatMessage, Model, NodeHealth, StreamEvent } from "@/types/chat";
import { streamSSE } from "@/lib/utils/sse-parser";

const API_BASE = "/api/backend";

export async function* sendChatStream(
  messages: Pick<ChatMessage, "role" | "content">[],
  model: string = "swarm-standard",
  signal?: AbortSignal,
  sessionId?: string,
  memoryEnabled: boolean = false,
): AsyncGenerator<StreamEvent, void, unknown> {
  const response = await fetch(`${API_BASE}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, stream: true, session_id: sessionId, memory_enabled: memoryEnabled }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status} ${response.statusText}`);
  }

  yield* streamSSE(response);
}

export async function compactChat(
  messages: Pick<ChatMessage, "role" | "content">[],
  model: string,
): Promise<{ messages: Pick<ChatMessage, "role" | "content">[]; summary: string; compacted: boolean }> {
  const response = await fetch(`${API_BASE}/v1/chat/compact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, model }),
  });
  if (!response.ok) {
    throw new Error(`Compact API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function summarizeSession(
  messages: Pick<ChatMessage, "role" | "content">[],
  topic: string,
  model: string,
): Promise<{ summary: string; saved: boolean }> {
  const response = await fetch(`${API_BASE}/v1/chat/summarize-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, topic, model }),
  });
  if (!response.ok) {
    throw new Error(`Summarize API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function saveSessionSummary(dateKey: string, topic: string, summary: string): Promise<void> {
  const response = await fetch(`${API_BASE}/v1/memory/session-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date_key: dateKey, topic, summary }),
  });
  if (!response.ok) {
    throw new Error(`Save summary API error: ${response.status} ${response.statusText}`);
  }
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
