"use client";

import { useCallback, useRef, useState } from "react";
import { sendChatStream } from "@/lib/api/chat";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { FileAttachment } from "@/types/chat";

const FIRST_TOKEN_TIMEOUT_MS = 60_000;
const STREAM_TIMEOUT_MS = 180_000;

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [latestThought, setLatestThought] = useState<string | null>(null);
  const [streamMode, setStreamMode] = useState<string>("content");
  const [tokenUsage, setTokenUsage] = useState({ used: 0, total: 128000, pct: 0 });
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
    async (content: string, attachments?: FileAttachment[]) => {
      if (!content.trim() || isStreaming) return;

      // Placeholder: attachments are accepted for API compatibility while upload
      // transport is finalized in a later pass.
      void attachments;

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
      setStatusMessage("Thinking...");
      setStreamMode("thinking");
      setLatestThought(null);
      const controller = new AbortController();
      abortRef.current = controller;
      let receivedAnyDelta = false;

      const firstTokenTimer = setTimeout(() => {
        if (!receivedAnyDelta) {
          setStatusMessage("Model is taking longer than usual...");
        }
      }, FIRST_TOKEN_TIMEOUT_MS);

      const streamTimer = setTimeout(() => {
        controller.abort("stream-timeout");
      }, STREAM_TIMEOUT_MS);

      try {
        let totalTokens = 0;
        for await (const delta of sendChatStream(apiMessages, model, controller.signal)) {
          receivedAnyDelta = true;
          if (statusMessage !== null) {
            setStatusMessage(null);
            setStreamMode("content");
          }
          appendToMessage(convId!, assistantId, delta);
          totalTokens += delta.length / 4; // rough token estimate
        }
        setTokenUsage((prev) => {
          const used = Math.min(prev.total, Math.round(prev.used + totalTokens));
          return { ...prev, used, pct: used / prev.total };
        });

        if (!receivedAnyDelta) {
          appendToMessage(
            convId!,
            assistantId,
            "*No response content was returned by the backend. Please retry or switch model.*"
          );
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          const timedOut = controller.signal.reason === "stream-timeout";
          if (timedOut) {
            appendToMessage(
              convId!,
              assistantId,
              "\n\n*Error: response timed out after 3 minutes. Please retry or use a smaller prompt.*"
            );
          }
        } else {
          appendToMessage(convId!, assistantId, "\n\n*Error: Connection failed.*");
        }
      } finally {
        clearTimeout(firstTokenTimer);
        clearTimeout(streamTimer);
        setIsStreaming(false);
        setStatusMessage(null);
        setLatestThought(null);
        abortRef.current = null;
      }
    },
    [activeConversationId, createConversation, addMessage, appendToMessage, model, isStreaming, statusMessage]
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const compactConversation = useCallback(async () => {
    // Placeholder for future context compaction logic
  }, []);

  return {
    messages: activeConversation()?.messages || [],
    isStreaming,
    statusMessage,
    latestThought,
    streamMode,
    tokenUsage,
    sendMessage,
    compactConversation,
    stopGeneration,
  };
}
