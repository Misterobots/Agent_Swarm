export interface TurnMetadata {
  turnId: string;
  agentName?: string;
  streamModes?: string[];
}

export interface FileAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  dataUrl: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  turnMetadata?: TurnMetadata;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  model: string;
  createdAt: number;
  updatedAt: number;
  memoryEnabled?: boolean;
}

export interface ChatCompletionChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: {
    index: number;
    delta: { content?: string; role?: string };
    finish_reason: string | null;
  }[];
  hive_event?: HiveEvent;
}

/** Structured event from the Hive backend for rich UI rendering */
export interface HiveEvent {
  type: "status" | "log" | "error" | "message" | "response" | "artifact";
  content: string;
}

/** Parsed SSE stream event — either content text or a structured hive event */
export type StreamEvent =
  | { kind: "content"; text: string }
  | { kind: "hive"; event: HiveEvent };

export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
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
