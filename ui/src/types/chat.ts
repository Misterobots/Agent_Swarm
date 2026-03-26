export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  model: string;
  createdAt: number;
  updatedAt: number;
}

export interface ChatCompletionChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: {
    index: number;
    delta: { content?: string; role?: string; type?: "content" | "status" };
    finish_reason: string | null;
  }[];
}

export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

export interface StreamEvent {
  type: "content" | "status";
  content: string;
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
