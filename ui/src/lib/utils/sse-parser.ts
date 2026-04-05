import type { ChatCompletionChunk, StreamEvent } from "@/types/chat";

/**
 * Parse an SSE line from the OpenAI-compatible streaming API.
 * Returns the parsed chunk or null for non-data lines / [DONE].
 */
export function parseSSELine(line: string): ChatCompletionChunk | null {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith("data: ")) return null;

  const data = trimmed.slice(6);
  if (data === "[DONE]") return null;

  try {
    return JSON.parse(data) as ChatCompletionChunk;
  } catch {
    return null;
  }
}

/**
 * Async generator that reads an SSE response body and yields structured
 * StreamEvents. Each event is either:
 *   - { kind: "content", text } — assistant response text
 *   - { kind: "hive", event }  — structured pipeline/agent/tool event
 */
export async function* streamSSE(
  response: Response
): AsyncGenerator<StreamEvent, void, unknown> {
  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  function* processChunk(chunk: ChatCompletionChunk) {
    // Check for structured hive_event first
    if (chunk.hive_event) {
      yield { kind: "hive" as const, event: chunk.hive_event };
    }
    // Also yield any content delta (for response/message types)
    const content = chunk.choices[0]?.delta?.content;
    if (content) {
      yield { kind: "content" as const, text: content };
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const chunk = parseSSELine(line);
        if (chunk) {
          yield* processChunk(chunk);
        }
      }
    }

    // Process remaining buffer
    if (buffer.trim()) {
      const chunk = parseSSELine(buffer);
      if (chunk) {
        yield* processChunk(chunk);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
