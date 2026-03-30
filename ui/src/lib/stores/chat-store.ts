import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, Conversation, ThoughtEvent } from "@/types/chat";

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

  // Derived
  activeConversation: () => Conversation | undefined;

  // Actions
  createConversation: (model?: string) => string;
  setActiveConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  updateConversation: (id: string, patch: Partial<Conversation>) => void;
  addMessage: (conversationId: string, message: Omit<ChatMessage, "id" | "timestamp">) => string;
  updateMessage: (conversationId: string, messageId: string, content: string) => void;
  appendToMessage: (conversationId: string, messageId: string, delta: string) => void;
  setMessageThoughtTrace: (conversationId: string, messageId: string, thoughts: ThoughtEvent[]) => void;
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

      createConversation: (model = "swarm-standard") => {
        const id = generateId();
        const conv: Conversation = {
          id,
          title: "New Chat",
          messages: [],
          model,
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
            // Auto-title from first user message
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
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, content } : m
              ),
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
    }),
    { name: "hive-chats" }
  )
);
