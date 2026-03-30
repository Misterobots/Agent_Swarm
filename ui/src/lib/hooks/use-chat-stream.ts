"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { compactChat, saveSessionSummary, sendChatStream, summarizeSession } from "@/lib/api/chat";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { ThoughtEvent } from "@/types/chat";

const MODEL_WINDOWS: Record<string, number> = {
  "qwen2.5-coder:14b": 32768,
  "qwen2.5-coder:14b-instruct-q4_k_m": 32768,
  "qwen3.5:9b": 32768,
  "nemotron-mini": 4096,
  "llama3.2:3b": 8192,
  "default": 8192,
};

const AUTO_COMPACT_THRESHOLD = 0.95;

function tokenEstimate(text: string): number {
  return Math.max(1, Math.floor(text.length / 4));
}

function messageTokenEstimate(messages: Array<{ content: string }>): number {
  return messages.reduce((acc, m) => acc + tokenEstimate(m.content || "") + 4, 0);
}

function getTokenUsage(messages: Array<{ content: string }>, model: string) {
  const used = messageTokenEstimate(messages);
  const total = MODEL_WINDOWS[model] ?? MODEL_WINDOWS.default;
  return { used, total, pct: total > 0 ? used / total : 0 };
}

function genId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [latestThought, setLatestThought] = useState<string | null>(null);
  const [tokenUsage, setTokenUsage] = useState({ used: 0, total: MODEL_WINDOWS.default, pct: 0 });
  const abortRef = useRef<AbortController | null>(null);
  const thoughtTraceRef = useRef<ThoughtEvent[]>([]);

  const {
    conversations,
    activeConversationId,
    activeConversation,
    createConversation,
    updateConversation,
    addMessage,
    appendToMessage,
    setMessageThoughtTrace,
  } = useChatStore();

  const model = useSettingsStore((s) => s.model);

  useEffect(() => {
    const conv = activeConversation();
    const convModel = conv?.model || model;
    const usage = getTokenUsage(conv?.messages || [], convModel);
    setTokenUsage(usage);
  }, [conversations, activeConversation, model]);

  const compactConversation = useCallback(
    async (conversationId?: string) => {
      const convId = conversationId || activeConversationId;
      if (!convId) return false;

      const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
      if (!conv || conv.messages.length === 0) return false;

      const apiMessages = conv.messages.map((m) => ({ role: m.role, content: m.content }));
      const result = await compactChat(apiMessages, conv.model || model);
      if (!result.compacted) return false;

      const baseTs = Date.now();
      updateConversation(convId, {
        messages: result.messages.map((m, idx) => ({
          id: genId(),
          role: m.role,
          content: m.content,
          timestamp: baseTs + idx,
        })),
      });

      addMessage(convId, {
        role: "assistant",
        content: "Context compacted to keep conversation quality high.",
      });
      return true;
    },
    [activeConversationId, addMessage, model, updateConversation]
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      // Ensure we have an active conversation
      let convId = activeConversationId;
      if (!convId) {
        const prevState = useChatStore.getState();
        const prev = prevState.conversations.find((c) => c.id === prevState.activeConversationId);
        if (prev && prev.memoryEnabled && prev.messages.length >= 8) {
          try {
            const summaryResp = await summarizeSession(
              prev.messages.map((m) => ({ role: m.role, content: m.content })),
              prev.title || "general",
              prev.model || model
            );
            if (summaryResp.summary) {
              const dateKey = new Date().toISOString().slice(0, 10);
              await saveSessionSummary(dateKey, prev.title || "general", summaryResp.summary);
            }
          } catch {
            // Memory persistence is best-effort.
          }
        }
        convId = createConversation(model);
      }

      const beforeConv = useChatStore.getState().conversations.find((c) => c.id === convId);
      if (beforeConv) {
        const beforeUsage = getTokenUsage(beforeConv.messages, beforeConv.model || model);
        if (beforeUsage.pct >= AUTO_COMPACT_THRESHOLD) {
          try {
            await compactConversation(convId);
          } catch {
            // If compact fails, continue with normal flow.
          }
        }
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
      const memoryEnabled = conv?.memoryEnabled ?? false;

      // Stream response
      setIsStreaming(true);
      setStatusMessage(null);
      setLatestThought(null);
      thoughtTraceRef.current = [];
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of sendChatStream(apiMessages, model, controller.signal, convId, memoryEnabled)) {
          if (event.type === "status") {
            setStatusMessage(event.content);
          } else if (event.type === "thought") {
            const thought: ThoughtEvent = { content: event.content, timestamp: Date.now() };
            thoughtTraceRef.current = [...thoughtTraceRef.current, thought];
            setLatestThought(event.content);
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
        if (thoughtTraceRef.current.length > 0) {
          setMessageThoughtTrace(convId!, assistantId, thoughtTraceRef.current);
        }
        setIsStreaming(false);
        setStatusMessage(null);
        setLatestThought(null);
        thoughtTraceRef.current = [];
        abortRef.current = null;
      }
    },
    [
      activeConversationId,
      compactConversation,
      createConversation,
      addMessage,
      appendToMessage,
      model,
      isStreaming,
      setMessageThoughtTrace,
    ]
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    messages: activeConversation()?.messages || [],
    isStreaming,
    statusMessage,
    latestThought,
    tokenUsage,
    sendMessage,
    compactConversation,
    stopGeneration,
  };
}
