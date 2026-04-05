"use client";

import { useCallback, useRef, useState } from "react";
import { sendChatStream } from "@/lib/api/chat";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { FileAttachment, HiveEvent } from "@/types/chat";

const FIRST_TOKEN_TIMEOUT_MS = 60_000;
const STREAM_TIMEOUT_MS = 180_000;

/** A single step in the agent pipeline displayed in the ThinkingIndicator */
export interface PipelineStep {
  id: number;
  type: HiveEvent["type"];
  agent: string;
  action: string;
  timestamp: number;
}

/** Parse a raw hive_event content string into agent + action */
function parseAgentStep(raw: string): { agent: string; action: string } {
  // Strip leading emojis
  let s = raw.replace(/^[\p{Emoji_Presentation}\p{Emoji}\uFE0F\u200D]+\s*/gu, "");
  // Handle [Bracket] tags: "[Router] Intent: ..." → agent: "Router", action: "Intent: ..."
  const bracketMatch = s.match(/^\[(.+?)\]\s*(.*)/);
  if (bracketMatch) {
    return { agent: bracketMatch[1], action: bracketMatch[2] };
  }
  // Handle "Agent Name: action..."
  const colonIdx = s.indexOf(":");
  if (colonIdx > 0 && colonIdx < 40) {
    return { agent: s.slice(0, colonIdx).trim(), action: s.slice(colonIdx + 1).trim() };
  }
  return { agent: "System", action: s };
}

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [latestThought, setLatestThought] = useState<string | null>(null);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [streamPhase, setStreamPhase] = useState<"idle" | "thinking" | "responding">("idle");
  const [tokenUsage, setTokenUsage] = useState({ used: 0, total: 128000, pct: 0 });
  const abortRef = useRef<AbortController | null>(null);
  const stepIdRef = useRef(0);

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
      void attachments;

      let convId = activeConversationId;
      if (!convId) {
        convId = createConversation(model);
      }

      addMessage(convId, { role: "user", content });
      const assistantId = addMessage(convId, { role: "assistant", content: "" });

      const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
      const apiMessages = (conv?.messages || [])
        .filter((m) => m.id !== assistantId)
        .map((m) => ({ role: m.role, content: m.content }));

      setIsStreaming(true);
      setStatusMessage("Initializing pipeline...");
      setStreamPhase("thinking");
      setLatestThought(null);
      setPipelineSteps([]);
      stepIdRef.current = 0;

      const controller = new AbortController();
      abortRef.current = controller;
      let receivedAnyContent = false;

      const firstTokenTimer = setTimeout(() => {
        if (!receivedAnyContent) {
          setStatusMessage("Model is taking longer than usual...");
        }
      }, FIRST_TOKEN_TIMEOUT_MS);

      const streamTimer = setTimeout(() => {
        controller.abort("stream-timeout");
      }, STREAM_TIMEOUT_MS);

      try {
        let totalTokens = 0;

        for await (const event of sendChatStream(apiMessages, model, controller.signal)) {
          if (event.kind === "hive") {
            // Structured pipeline event from the backend
            const { type, content: raw } = event.event;

            if (type === "status" || type === "log") {
              const { agent, action } = parseAgentStep(raw);
              const step: PipelineStep = {
                id: ++stepIdRef.current,
                type,
                agent,
                action,
                timestamp: Date.now(),
              };
              setPipelineSteps((prev) => [...prev, step]);
              setStatusMessage(`${agent}: ${action}`);
              setLatestThought(action);
            } else if (type === "error") {
              const { agent, action } = parseAgentStep(raw);
              const step: PipelineStep = {
                id: ++stepIdRef.current,
                type: "error",
                agent,
                action,
                timestamp: Date.now(),
              };
              setPipelineSteps((prev) => [...prev, step]);
              setStatusMessage(`Error: ${raw}`);
            }
            // artifact events are handled via content below
          } else if (event.kind === "content") {
            // Actual assistant response text
            const text = event.text;
            if (text.replace(/\s/g, "").length > 0) {
              if (!receivedAnyContent) {
                receivedAnyContent = true;
                setStreamPhase("responding");
                setStatusMessage(null);
              }
              appendToMessage(convId!, assistantId, text);
              totalTokens += text.length / 4;
            }
          }
        }

        setTokenUsage((prev) => {
          const used = Math.min(prev.total, Math.round(prev.used + totalTokens));
          return { ...prev, used, pct: used / prev.total };
        });

        if (!receivedAnyContent) {
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
        setStreamPhase("idle");
        // Keep pipelineSteps visible — cleared on next send
        abortRef.current = null;
      }
    },
    [activeConversationId, createConversation, addMessage, appendToMessage, model, isStreaming]
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
    pipelineSteps,
    streamPhase,
    tokenUsage,
    sendMessage,
    compactConversation,
    stopGeneration,
  };
}
