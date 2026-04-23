import type { StreamEvent, TurnMetadata } from "@/types/chat";

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
      type?: "content" | "status" | "thought" | "plan" | "log" | "tool_call" | "tool_start" | "tool_progress" | "tool_result" | "tool_approval_needed" | "stream_mode" | "turn_boundary" | "turn_metadata" | "continuation" | "error" | "swarm_phase" | "swarm_worker_created" | "swarm_task_list";
      // Swarm theater fields
      phase_num?: number;
      phase_name?: string;
      total_phases?: number;
      worker_id?: string;
      role?: string;
      pioneer_name?: string;
      pioneer_full_name?: string;
      pioneer_motto?: string;
      task?: string;
      workers?: Array<Record<string, unknown>>;
      tool_name?: string;
      tool_input?: Record<string, unknown>;
      tool_call_id?: string;
      tool_state?: "queued" | "executing" | "completed" | "error" | "cancelled";
      tool_progress?: number;
      tool_output?: string;
      streamMode?: "thinking" | "responding" | "tool-use" | "requesting" | "compacting";
      turnId?: string;
      turnMetadata?: Record<string, unknown>;
      continuationHint?: "auto_continue" | "await_user" | "compacting";
      resumeToken?: string;
      artifacts?: Array<Record<string, unknown>>;
      errorCode?: string;
      errorDetails?: string;
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
 * Supports both legacy (content, status, thought, tool_call) and new event types (tool_start, tool_progress, tool_result, turn_metadata, stream_mode, continuation).
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
          if (!delta) continue;

          // Tool lifecycle events (new)
          if (delta.type === "tool_start") {
            yield {
              type: "tool_start",
              content: `Starting tool: ${delta.tool_name}`,
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_input: delta.tool_input,
              tool_state: "queued",
            };
          } else if (delta.type === "tool_progress") {
            yield {
              type: "tool_progress",
              content: delta.content || `${delta.tool_name} in progress...`,
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_state: "executing",
              tool_progress: delta.tool_progress || 0,
            };
          } else if (delta.type === "tool_result") {
            yield {
              type: "tool_result",
              content: delta.tool_output || delta.content || "Tool executed",
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_output: delta.tool_output,
              tool_state: "completed",
              artifacts: delta.artifacts as any,
            };
          } else if (delta.type === "tool_approval_needed") {
            yield {
              type: "tool_approval_needed",
              content: delta.content || `Approval required: ${delta.tool_name}`,
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_input: delta.tool_input,
            };
          }
          // Stream state events (new)
          else if (delta.type === "stream_mode") {
            yield {
              type: "stream_mode",
              content: delta.content || `Stream mode: ${delta.streamMode}`,
              streamMode: delta.streamMode,
            };
          }
          // Turn coordination events (new)
          else if (delta.type === "turn_boundary") {
            yield {
              type: "turn_boundary",
              content: delta.content || `Turn complete`,
              turnId: delta.turnId,
            };
          } else if (delta.type === "turn_metadata") {
            const metadata = delta.turnMetadata as TurnMetadata | undefined;
            yield {
              type: "turn_metadata",
              content: delta.content || "Turn metadata",
              turnId: delta.turnId,
              turnMetadata: metadata,
            };
          }
          // Continuation hints (new)
          else if (delta.type === "continuation") {
            yield {
              type: "continuation",
              content: delta.content || "Ready to continue",
              continuationHint: delta.continuationHint,
            };
          }
          // Swarm theater events
          else if (delta.type === "swarm_phase") {
            yield {
              type: "swarm_phase",
              content: delta.content || "",
              phase_num: delta.phase_num,
              phase_name: delta.phase_name,
              total_phases: delta.total_phases,
            };
          } else if (delta.type === "swarm_worker_created") {
            yield {
              type: "swarm_worker_created",
              content: delta.content || "",
              worker_id: delta.worker_id,
              role: delta.role,
              pioneer_name: delta.pioneer_name,
              pioneer_full_name: delta.pioneer_full_name,
              pioneer_motto: delta.pioneer_motto,
              task: delta.task,
            };
          } else if (delta.type === "swarm_task_list") {
            yield {
              type: "swarm_task_list",
              content: delta.content || "",
              workers: delta.workers as any,
            };
          }
          // Legacy tool call format (backward compatible)
          else if (delta.type === "tool_call") {
            yield {
              type: "tool_call",
              content: delta.content || "",
              tool_name: delta.tool_name,
              tool_input: delta.tool_input,
              tool_call_id: delta.tool_call_id,
            };
          }
          // Standard content/status/thought/plan/log (backward compatible)
          else if (delta.content) {
            const knownTypes = ["status", "thought", "plan", "log", "error"] as const;
            const mappedType = (knownTypes as readonly string[]).includes(delta.type || "")
              ? (delta.type as "status" | "thought" | "plan" | "log" | "error")
              : "content";
            yield {
              type: mappedType,
              content: delta.content,
            };
          }
          // Error events
          else if (delta.type === "error") {
            yield {
              type: "error",
              content: delta.content || "Stream error occurred",
              errorCode: delta.errorCode,
              errorDetails: delta.errorDetails,
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
        if (delta) {
          // Same parsing logic as above
          if (delta.type === "tool_start") {
            yield {
              type: "tool_start",
              content: `Starting tool: ${delta.tool_name}`,
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_input: delta.tool_input,
              tool_state: "queued",
            };
          } else if (delta.type === "tool_progress") {
            yield {
              type: "tool_progress",
              content: delta.content || `${delta.tool_name} in progress...`,
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_state: "executing",
              tool_progress: delta.tool_progress || 0,
            };
          } else if (delta.type === "tool_result") {
            yield {
              type: "tool_result",
              content: delta.tool_output || delta.content || "Tool executed",
              tool_name: delta.tool_name,
              tool_call_id: delta.tool_call_id,
              tool_output: delta.tool_output,
              tool_state: "completed",
              artifacts: delta.artifacts as any,
            };
          } else if (delta.type === "stream_mode") {
            yield {
              type: "stream_mode",
              content: delta.content || `Stream mode: ${delta.streamMode}`,
              streamMode: delta.streamMode,
            };
          } else if (delta.type === "turn_boundary") {
            yield {
              type: "turn_boundary",
              content: delta.content || `Turn complete`,
              turnId: delta.turnId,
            };
          } else if (delta.type === "turn_metadata") {
            const metadata = delta.turnMetadata as TurnMetadata | undefined;
            yield {
              type: "turn_metadata",
              content: delta.content || "Turn metadata",
              turnId: delta.turnId,
              turnMetadata: metadata,
            };
          } else if (delta.type === "continuation") {
            yield {
              type: "continuation",
              content: delta.content || "Ready to continue",
              continuationHint: delta.continuationHint,
            };
          } else if (delta.type === "tool_call") {
            yield {
              type: "tool_call",
              content: delta.content || "",
              tool_name: delta.tool_name,
              tool_input: delta.tool_input,
              tool_call_id: delta.tool_call_id,
            };
          } else if (delta.content) {
            const knownTypes = ["status", "thought", "plan", "log", "error"] as const;
            const mappedType = (knownTypes as readonly string[]).includes(delta.type || "")
              ? (delta.type as "status" | "thought" | "plan" | "log" | "error")
              : "content";
            yield {
              type: mappedType,
              content: delta.content,
            };
          } else if (delta.type === "error") {
            yield {
              type: "error",
              content: delta.content || "Stream error occurred",
              errorCode: delta.errorCode,
              errorDetails: delta.errorDetails,
            };
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
