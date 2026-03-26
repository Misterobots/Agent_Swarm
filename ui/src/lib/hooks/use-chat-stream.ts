"use client";

import { useCallback, useRef, useState } from "react";
import { sendChatStream } from "@/lib/api/chat";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const {
    activeConversationId,
    activeConversation,
    createConversation,
    addMessage,
    appendToMessage,
  } = useChatStore();

  const model = useSettingsStore((s) => s.model);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      // Ensure we have an active conversation
      let convId = activeConversationId;
      if (!convId) {
        convId = createConversation(model);
      }

      // Add user message
      addMessage(convId, { role: "user", content });

      // Create assistant message placeholder
      const assistantId = addMessage(convId, { role: "assistant", content: "" });

      // Build messages array for the API
      const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
      const apiMessages = (conv?.messages || [])
        .filter((m) => m.id !== assistantId)
        .map((m) => ({ role: m.role, content: m.content }));

      // Stream response
      setIsStreaming(true);
      setStatusMessage(null);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of sendChatStream(apiMessages, model, controller.signal, convId)) {
          if (event.type === "status") {
            setStatusMessage(event.content);
          } else {
            // Clear status once real content arrives
            setStatusMessage(null);
            appendToMessage(convId!, assistantId, event.content);
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          // User cancelled
        } else {
          appendToMessage(convId!, assistantId, "\n\n*Error: Connection failed.*");
        }
      } finally {
        setIsStreaming(false);
        setStatusMessage(null);
        abortRef.current = null;
      }
    },
    [activeConversationId, createConversation, addMessage, appendToMessage, model, isStreaming]
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    messages: activeConversation()?.messages || [],
    isStreaming,
    statusMessage,
    sendMessage,
    stopGeneration,
  };
}
