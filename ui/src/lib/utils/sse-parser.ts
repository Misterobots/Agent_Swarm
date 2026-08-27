import type {
  AgentTraceEvent,
  Artifact,
  CadArtifact,
  ClarificationCard,
  DesignArtifact,
  FileChange,
  MediaAttachment,
  QueueStatus,
  StreamEvent,
  SuggestedFollowup,
  TodoItem,
  TurnMetadata,
  WorkshopQuestion,
  WorkflowNextStep,
} from "@/types/chat";

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
      type?: "content" | "status" | "thought" | "plan" | "log" | "tool_call" | "tool_start" | "tool_progress" | "tool_result" | "tool_approval_needed" | "stream_mode" | "turn_boundary" | "turn_metadata" | "continuation" | "error" | "swarm_phase" | "swarm_worker_created" | "swarm_task_list" | "clarification_card" | "media_attachment" | "design_artifact" | "cad_artifact" | "workshop_questions" | "workflow_next_steps" | "suggested_followups" | "agent_event" | "set_preview_url" | "model_queue_status" | "preview_unavailable" | "heartbeat" | "file_change" | "todo" | "usage";
      // Swarm theater fields
      phase_num?: number;
      phase_name?: string;
      total_phases?: number;
      worker_id?: string;
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
  usage?: {
    prompt_tokens:     number;
    completion_tokens: number;
    total_tokens:      number;
    prompt_chars:      number;
    completion_chars:  number;
  };
}

type ChunkDelta = ChatCompletionChunk["choices"][number]["delta"];

interface StructuredContent {
  questions?: WorkshopQuestion[];
  loading?: boolean;
  steps?: WorkflowNextStep[];
  todos?: TodoItem[];
}

type StructuredChunkDelta = Omit<ChunkDelta, "content"> & {
  content?: string | StructuredContent;
  clarification?: ClarificationCard;
  followups?: SuggestedFollowup[];
  agent_name?: string;
  event_type?: AgentTraceEvent["eventType"];
  url?: string;
  cad_artifact?: CadArtifact;
};

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
 * Map a single SSE chunk delta to a typed StreamEvent (or null for no-op).
 *
 * SINGLE SOURCE OF TRUTH — used by both the line loop and the trailing-buffer
 * path in streamSSE so the two dispatch sites can no longer drift (they were
 * previously copy-pasted and had already diverged by four event types).
 * `chunk` is passed because token usage is carried on the chunk, not the delta.
 */
function deltaToStreamEvent(
  delta: ChunkDelta,
  chunk: ChatCompletionChunk
): StreamEvent | null {
  const structured = delta as unknown as StructuredChunkDelta;
  const payload = typeof structured.content === "object" && structured.content !== null
    ? structured.content
    : {};

  // Tool lifecycle events
  if (delta.type === "tool_start") {
    return {
      type: "tool_start",
      content: `Starting tool: ${delta.tool_name}`,
      tool_name: delta.tool_name,
      tool_call_id: delta.tool_call_id,
      tool_input: delta.tool_input,
      tool_state: "queued",
    };
  }
  if (delta.type === "tool_progress") {
    return {
      type: "tool_progress",
      content: delta.content || `${delta.tool_name} in progress...`,
      tool_name: delta.tool_name,
      tool_call_id: delta.tool_call_id,
      tool_state: "executing",
      tool_progress: delta.tool_progress || 0,
    };
  }
  if (delta.type === "tool_result") {
    return {
      type: "tool_result",
      content: delta.tool_output || delta.content || "Tool executed",
      tool_name: delta.tool_name,
      tool_call_id: delta.tool_call_id,
      tool_output: delta.tool_output,
      tool_state: "completed",
      artifacts: delta.artifacts as unknown as Artifact[],
    };
  }
  if (delta.type === "tool_approval_needed") {
    return {
      type: "tool_approval_needed",
      content: delta.content || `Approval required: ${delta.tool_name}`,
      tool_name: delta.tool_name,
      tool_call_id: delta.tool_call_id,
      tool_input: delta.tool_input,
    };
  }
  // Stream state
  if (delta.type === "stream_mode") {
    return {
      type: "stream_mode",
      content: delta.content || `Stream mode: ${delta.streamMode}`,
      streamMode: delta.streamMode,
    };
  }
  // Turn coordination
  if (delta.type === "turn_boundary") {
    return {
      type: "turn_boundary",
      content: delta.content || `Turn complete`,
      turnId: delta.turnId,
    };
  }
  if (delta.type === "turn_metadata") {
    return {
      type: "turn_metadata",
      content: delta.content || "Turn metadata",
      turnId: delta.turnId,
      turnMetadata: delta.turnMetadata as TurnMetadata | undefined,
    };
  }
  if (delta.type === "continuation") {
    return {
      type: "continuation",
      content: delta.content || "Ready to continue",
      continuationHint: delta.continuationHint,
    };
  }
  // Clarification / media / design cards
  if (delta.type === "clarification_card") {
    return { type: "clarification_card", content: "", clarification: structured.clarification };
  }
  if (delta.type === "media_attachment") {
    return { type: "media_attachment", content: "", media: structured.content as MediaAttachment };
  }
  if (delta.type === "design_artifact") {
    return { type: "design_artifact", content: "", design: structured.content as DesignArtifact };
  }
  if (delta.type === "cad_artifact") {
    return { type: "cad_artifact", content: "", cadArtifact: structured.cad_artifact };
  }
  // Workshop pipeline
  if (delta.type === "workshop_questions") {
    return {
      type: "workshop_questions",
      content: "",
      workshopQuestions: payload.questions ?? [],
      workshopQuestionsLoading: payload.loading ?? false,
    };
  }
  if (delta.type === "workflow_next_steps") {
    return {
      type: "workflow_next_steps",
      content: "",
      workflowNextSteps: payload.steps ?? [],
    };
  }
  if (delta.type === "suggested_followups") {
    return { type: "suggested_followups", content: "", followups: structured.followups || [] };
  }
  // Structured agent trace event
  if (delta.type === "agent_event") {
    return {
      type: "agent_event",
      content: delta.content || "",
      agentEvent: {
        agent: structured.agent_name || "Agent",
        eventType: structured.event_type || "status",
        content: delta.content || "",
        timestamp: Date.now(),
      },
    };
  }
  // Agent pushes a URL into the preview pane
  if (delta.type === "set_preview_url") {
    return { type: "set_preview_url", content: "", url: structured.url || (typeof structured.content === "string" ? structured.content : "") };
  }
  // Model queue status — emitted before GPU lock acquisition
  if (delta.type === "model_queue_status") {
    return { type: "model_queue_status", content: "", queueStatus: structured.content as QueueStatus };
  }
  // Swarm theater events
  if (delta.type === "swarm_phase") {
    return {
      type: "swarm_phase",
      content: delta.content || "",
      phase_num: delta.phase_num,
      phase_name: delta.phase_name,
      total_phases: delta.total_phases,
    };
  }
  if (delta.type === "swarm_worker_created") {
    return {
      type: "swarm_worker_created",
      content: delta.content || "",
      worker_id: delta.worker_id,
      role: delta.role,
      pioneer_name: delta.pioneer_name,
      pioneer_full_name: delta.pioneer_full_name,
      pioneer_motto: delta.pioneer_motto,
      task: delta.task,
    };
  }
  if (delta.type === "swarm_task_list") {
    return { type: "swarm_task_list", content: delta.content || "", workers: delta.workers as unknown as import("@/types/chat").SwarmWorker[] };
  }
  // File-system activity chips from swarm workers
  if (delta.type === "file_change") {
    return {
      type: "file_change",
      content: "",
      fileChange: structured.content as FileChange,
    };
  }
  // Agent todo list (TodoWrite) — full list each update
  if (delta.type === "todo") {
    return { type: "todo", content: "", todos: payload.todos ?? [] };
  }
  // Legacy tool call format (backward compatible)
  if (delta.type === "tool_call") {
    return {
      type: "tool_call",
      content: delta.content || "",
      tool_name: delta.tool_name,
      tool_input: delta.tool_input,
      tool_call_id: delta.tool_call_id,
    };
  }
  // Server-reported token usage — carried on the chunk, delta.content is empty
  if (delta.type === "usage") {
    return { type: "usage", content: "", usage: chunk.usage };
  }
  // Error — checked BEFORE the generic content fallback so an error event that
  // carries content keeps its errorCode / errorDetails instead of being
  // demoted to a plain content event.
  if (delta.type === "error") {
    return {
      type: "error",
      content: delta.content || "Stream error occurred",
      errorCode: delta.errorCode,
      errorDetails: delta.errorDetails,
    };
  }
  // Standard content/status/thought/plan/log (backward compatible)
  if (delta.content) {
    const knownTypes = ["status", "thought", "plan", "log", "error"] as const;
    const mappedType = (knownTypes as readonly string[]).includes(delta.type || "")
      ? (delta.type as "status" | "thought" | "plan" | "log" | "error")
      : "content";
    return { type: mappedType, content: delta.content };
  }
  return null;
}

/**
 * Async generator that reads an SSE response body and yields typed stream events.
 * Both the per-line loop and the trailing-buffer tail delegate to
 * deltaToStreamEvent so all event types are handled identically in both paths.
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
        if (!chunk) continue;
        const delta = chunk.choices[0]?.delta;
        if (!delta) continue;
        const event = deltaToStreamEvent(delta, chunk);
        if (event) yield event;
      }
    }

    // Process remaining buffer (a final event line with no trailing newline)
    if (buffer.trim()) {
      const chunk = parseSSELine(buffer);
      if (chunk) {
        const delta = chunk.choices[0]?.delta;
        const event = delta ? deltaToStreamEvent(delta, chunk) : null;
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
