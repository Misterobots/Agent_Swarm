import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  ChatMessage,
  ClarificationCard,
  Conversation,
  MediaAttachment,
  ThoughtEvent,
  ToolCallEvent,
  ToolLifecycleEvent,
  ToolResult,
  TurnMetadata,
} from "@/types/chat";

function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Array.from(crypto.getRandomValues(new Uint8Array(16)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/, "$1-$2-$3-$4-$5");
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversation: () => Conversation | undefined;
  createConversation: (model?: string) => string;
  setActiveConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  replaceConversations: (conversations: Conversation[]) => void;
  updateConversation: (id: string, patch: Partial<Conversation>) => void;
  addMessage: (conversationId: string, message: Omit<ChatMessage, "id" | "timestamp">) => string;
  updateMessage: (conversationId: string, messageId: string, content: string) => void;
  appendToMessage: (conversationId: string, messageId: string, delta: string) => void;
  setMessageThoughtTrace: (conversationId: string, messageId: string, thoughts: ThoughtEvent[]) => void;
  setMessageToolCalls: (conversationId: string, messageId: string, toolCalls: ToolCallEvent[]) => void;
  setMessageToolLifecycle: (conversationId: string, messageId: string, lifecycle: ToolLifecycleEvent[]) => void;
  setMessageToolResults: (conversationId: string, messageId: string, results: ToolResult[]) => void;
  setMessageTurnMetadata: (conversationId: string, messageId: string, metadata: TurnMetadata) => void;
  setMessagePendingApprovals: (conversationId: string, messageId: string, approvals: import("@/types/chat").ToolApprovalEvent[]) => void;
  setMessagePendingClarification: (conversationId: string, messageId: string, card: ClarificationCard | undefined) => void;
  setMessageMediaAttachments: (conversationId: string, messageId: string, attachments: MediaAttachment[]) => void;
  setMessageDesignArtifact: (conversationId: string, messageId: string, artifact: import("@/types/chat").DesignArtifact) => void;
  setMessageQueueStatus: (conversationId: string, messageId: string, status: import("@/types/chat").QueueStatus | undefined) => void;
  setMessageSuggestedFollowups: (conversationId: string, messageId: string, followups: import("@/types/chat").SuggestedFollowup[]) => void;
  setMessageFlaggedFollowup: (conversationId: string, messageId: string, followup: import("@/types/chat").FlaggedFollowup) => void;
  setMessageWorkshopQuestions: (conversationId: string, messageId: string, questions: import("@/types/chat").WorkshopQuestion[]) => void;
  setMessageWorkflowNextSteps: (conversationId: string, messageId: string, steps: import("@/types/chat").WorkflowNextStep[]) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,

      activeConversation: () => {
        const state = get();
        return state.conversations.find((c) => c.id === state.activeConversationId);
      },

      createConversation: (model = "memex") => {
        const id = generateId();
        const conv: Conversation = {
          id,
          title: "New Chat",
          messages: [],
          model,
          memoryEnabled: true,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        set((state) => ({
          conversations: [conv, ...state.conversations],
          activeConversationId: id,
        }));
        return id;
      },

      setActiveConversation: (id) => set({ activeConversationId: id }),

      replaceConversations: (conversations) =>
        set((state) => ({
          conversations,
          // Preserve active conversation if it exists in the new list.
          // If it doesn't (user switch / stale ID), fall back to first or null.
          activeConversationId: conversations.some((c) => c.id === state.activeConversationId)
            ? state.activeConversationId
            : (conversations[0]?.id ?? null),
        })),

      deleteConversation: (id) =>
        set((state) => {
          const filtered = state.conversations.filter((c) => c.id !== id);
          return {
            conversations: filtered,
            activeConversationId:
              state.activeConversationId === id
                ? filtered[0]?.id || null
                : state.activeConversationId,
          };
        }),

      updateConversation: (id, patch) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, ...patch, updatedAt: Date.now() } : c
          ),
        })),

      addMessage: (conversationId, message) => {
        const msgId = generateId();
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            const newMsg: ChatMessage = {
              ...message,
              id: msgId,
              timestamp: Date.now(),
            };
            const title =
              c.messages.length === 0 && message.role === "user"
                ? message.content.slice(0, 40) + (message.content.length > 40 ? "..." : "")
                : c.title;
            return {
              ...c,
              title,
              messages: [...c.messages, newMsg],
              updatedAt: Date.now(),
            };
          }),
        }));
        return msgId;
      },

      updateMessage: (conversationId, messageId, content) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) => (m.id === messageId ? { ...m, content } : m)),
              updatedAt: Date.now(),
            };
          }),
        })),

      appendToMessage: (conversationId, messageId, delta) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, content: m.content + delta } : m
              ),
            };
          }),
        })),

      setMessageThoughtTrace: (conversationId, messageId, thoughts) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, thoughtTrace: thoughts } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageToolCalls: (conversationId, messageId, toolCalls) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) => (m.id === messageId ? { ...m, toolCalls } : m)),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageToolLifecycle: (conversationId, messageId, lifecycle) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, toolLifecycle: lifecycle } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageToolResults: (conversationId, messageId, results) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, toolResults: results } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageTurnMetadata: (conversationId, messageId, metadata) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, turnMetadata: metadata } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessagePendingApprovals: (conversationId, messageId, approvals) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, pendingApprovals: approvals } : m
              ),
            };
          }),
        })),

      setMessagePendingClarification: (conversationId, messageId, card) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, pendingClarification: card } : m
              ),
            };
          }),
        })),

      setMessageMediaAttachments: (conversationId, messageId, attachments) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, mediaAttachments: attachments } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageDesignArtifact: (conversationId, messageId, artifact) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, designArtifact: artifact } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageQueueStatus: (conversationId, messageId, status) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, pendingQueueStatus: status } : m
              ),
            };
          }),
        })),

      setMessageSuggestedFollowups: (conversationId, messageId, followups) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, suggestedFollowups: followups } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageFlaggedFollowup: (conversationId, messageId, followup) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, flaggedFollowup: followup } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageWorkshopQuestions: (conversationId, messageId, questions) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, workshopQuestions: questions } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),

      setMessageWorkflowNextSteps: (conversationId, messageId, steps) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, workflowNextSteps: steps } : m
              ),
              updatedAt: Date.now(),
            };
          }),
        })),
    }),
    { name: "memex-chats" }
  )
);
