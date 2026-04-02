import type { StreamEvent } from "@/types/chat";

export interface ChatCompletionChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: {
    index: number;
    delta: {
      content?: string;
      role?: string;
      type?: "content" | "status" | "thought" | "tool_call";
      tool_name?: string;
      tool_input?: Record<string, unknown>;
      tool_call_id?: string;
    };
    finish_reason: string | null;
  }[];
}
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
 * Async generator that reads an SSE response body and yields typed stream events.
 */
export async function* streamSSE(
  response: Response
): AsyncGenerator<StreamEvent, void, unknown> {
  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

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
          const delta = chunk.choices[0]?.delta;
          if (delta?.type === "tool_call") {
            yield {
              type: "tool_call",
              content: delta.content || "",
              tool_name: delta.tool_name,
              tool_input: delta.tool_input,
              tool_call_id: delta.tool_call_id,
            };
          } else if (delta?.content) {
            yield {
              type: delta.type === "status" || delta.type === "thought" ? delta.type : "content",
              content: delta.content,
            };
          }
        }
      }
    }

    // Process remaining buffer
    if (buffer.trim()) {
      const chunk = parseSSELine(buffer);
      if (chunk) {
        const delta = chunk.choices[0]?.delta;
        if (delta?.type === "tool_call") {
          yield {
            type: "tool_call",
            content: delta.content || "",
            tool_name: delta.tool_name,
            tool_input: delta.tool_input,
            tool_call_id: delta.tool_call_id,
          };
        } else if (delta?.content) {
          yield {
            type: delta.type === "status" || delta.type === "thought" ? delta.type : "content",
            content: delta.content,
          };
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
