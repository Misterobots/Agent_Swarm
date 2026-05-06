/**
 * Stream mode indicates the current state of the LLM response stream.
 * Used for UI rendering of thinking indicators and stream progress.
 */
export type StreamMode = "thinking" | "responding" | "tool-use" | "requesting" | "compacting";

/** Skill hint sent to the router to bias intent classification. */
export type Skill = "general" | "code" | "devops" | "data" | "creative" | "research" | "explain";

/** Response style modifier injected into the system prompt. */
export type Style = "default" | "concise" | "explanatory" | "formal" | "technical" | "casual";

/** A file attached to a chat message (base64-encoded). */
export interface FileAttachment {
  name: string;
  mimeType: string;
  /** base64-encoded file content */
  data: string;
  /** size in bytes before encoding */
  size: number;
}

/**
 * Turn-level metadata for conversation continuity and resumption.
 */
export interface TurnMetadata {
  turnId: string;
  agentName?: string;
  streamModes: StreamMode[];
  toolsInvoked: string[];
  inContextTokens?: number;
  continuable: boolean;
  resumeToken?: string;
  traceId?: string;
}

/**
 * Tool state progression during execution.
 */
export type ToolState = "queued" | "executing" | "completed" | "error" | "cancelled";

/**
 * Live tool execution event with state and progress.
 */
export interface ToolLifecycleEvent {
  tool_call_id: string;
  tool_name: string;
  state: ToolState;
  input?: Record<string, unknown>;
  output?: string;
  error?: string;
  progress?: number;
  timestamp: number;
}

/**
 * Artifact represents a structured code/patch that can be applied or edited.
 */
export interface Artifact {
  id: string;
  type: "code" | "patch" | "document";
  language?: string;
  content: string;
  description?: string;
  actionable: boolean;
  appliedAt?: number;
}

/**
 * Tool result with structured output for rendering.
 */
export interface ToolResult {
  tool_call_id: string;
  tool_name: string;
  success: boolean;
  output: string;
  structuredOutput?: Record<string, unknown>;
  artifacts?: Artifact[];
  timestamp: number;
}

/**
 * Enriched stream event supporting tool lifecycle, continuity, and UI state.
 */
/** Worker info emitted by the Lamport coordinator. */
export interface SwarmWorker {
  worker_id: string;
  role: string;
  pioneer_name: string;
  pioneer_full_name?: string;
  pioneer_motto?: string;
  task: string;
  phase: string;
  state: "pending" | "running" | "completed" | "failed" | "cancelled";
  output?: string;
}

export interface ClarificationOption {
  label: string;
  value: string;
  description?: string;
  /** If set, router.push() to this path after selecting */
  redirect?: string;
}

export interface ClarificationCard {
  question: string;
  context?: string;
  options: ClarificationOption[];
  allow_freetext: boolean;
  card_type: "ambiguity" | "dev_project" | "onboarding" | "dev_mode_gate" | "art_direction";
}

export interface QueueStatus {
  model: string;
  tier: "small" | "large";
  is_loaded: boolean;
  queue_position: number;
  estimated_wait_s: number;
  alternatives: Array<{ name: string; description: string; vram_gb: number }>;
  should_prompt: boolean;
}

export interface StreamEvent {
  type: "content" | "status" | "thought" | "plan" | "log" | "tool_call" | "tool_start" | "tool_progress" | "tool_result" | "tool_approval_needed" | "stream_mode" | "turn_boundary" | "turn_metadata" | "continuation" | "error" | "swarm_phase" | "swarm_worker_created" | "swarm_task_list" | "clarification_card" | "media_attachment" | "model_queue_status";
  content?: string;
  // Swarm theater
  phase_num?: number;
  phase_name?: string;
  total_phases?: number;
  worker_id?: string;
  role?: string;
  pioneer_name?: string;
  pioneer_full_name?: string;
  pioneer_motto?: string;
  task?: string;
  workers?: SwarmWorker[];
  
  // Tool lifecycle
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_call_id?: string;
  tool_state?: ToolState;
  tool_progress?: number;
  tool_output?: string;
  artifacts?: Artifact[];
  
  // Stream state
  streamMode?: StreamMode;
  
  // Turn continuation
  turnId?: string;
  turnMetadata?: TurnMetadata;
  continuationHint?: "auto_continue" | "await_user" | "compacting";
  resumeToken?: string;
  
  // Error details
  errorCode?: string;
  errorDetails?: string;

  // Clarification card
  clarification?: ClarificationCard;

  // Media attachment
  media?: MediaAttachment;

  // Model queue status
  queueStatus?: QueueStatus;
}

/**
 * Generated media attachment (image, audio, video, etc.)
 */
export interface MediaAttachment {
  id: string;
  filename: string;
  mimeType: string;
  url: string;
  downloadUrl: string;
  size: number;
  width?: number;
  height?: number;
  duration?: number;
  previewable: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  thoughtTrace?: ThoughtEvent[];
  toolCalls?: ToolCallEvent[];
  toolLifecycle?: ToolLifecycleEvent[];
  toolResults?: ToolResult[];
  artifacts?: Artifact[];
  turnMetadata?: TurnMetadata;
  pendingApprovals?: ToolApprovalEvent[];
  pendingClarification?: ClarificationCard;
  mediaAttachments?: MediaAttachment[];
  pendingQueueStatus?: QueueStatus;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  model: string;
  createdAt: number;
  updatedAt: number;
  memoryEnabled?: boolean;
  lastTurnId?: string;
  resumeCheckpoints?: Array<{ turnId: string; timestamp: number; resumeToken?: string }>;
}

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
      type?: "content" | "status" | "thought" | "plan" | "tool_call" | "tool_start" | "tool_progress" | "tool_result" | "tool_approval_needed" | "stream_mode" | "turn_metadata" | "continuation";
      tool_name?: string;
      tool_input?: Record<string, unknown>;
      tool_call_id?: string;
      tool_state?: ToolState;
      tool_progress?: number;
      tool_output?: string;
      streamMode?: StreamMode;
      turnId?: string;
      turnMetadata?: TurnMetadata;
      continuationHint?: "auto_continue" | "await_user" | "compacting";
      resumeToken?: string;
    };
    finish_reason: string | null;
  }[];
}

export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
  label?: string;
  description?: string;
  context_window?: number;
}

export interface ToolCallEvent {
  tool_name: string;
  tool_input?: Record<string, unknown>;
  tool_call_id?: string;
  content: string;
  timestamp: number;
}

export interface ToolApprovalEvent {
  tool_call_id: string;
  tool_name: string;
  tool_input?: Record<string, unknown>;
  timestamp: number;
}

export interface ThoughtEvent {
  content: string;
  timestamp: number;
}

export interface NodeHealth {
  name: string;
  host: string;
  healthy: boolean;
  vram_mb: number;
  loaded_models: string[];
  available_models: string[];
  last_checked: number;
}
