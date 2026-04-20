"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { compactChat, saveSessionSummary, sendChatStream, summarizeSession } from "@/lib/api/chat";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { ThoughtEvent, ToolCallEvent, ToolLifecycleEvent, ToolResult, ToolApprovalEvent, TurnMetadata, StreamMode, FileAttachment } from "@/types/chat";

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

export function useChatStream(options?: {
  devMode?: boolean;
  onToolResult?: (toolName: string, toolInput: Record<string, unknown>, output: string) => void;
}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [latestThought, setLatestThought] = useState<string | null>(null);
  const [streamMode, setStreamMode] = useState<StreamMode | null>(null);
  const [tokenUsage, setTokenUsage] = useState({ used: 0, total: MODEL_WINDOWS.default, pct: 0 });
  const abortRef = useRef<AbortController | null>(null);
  const thoughtTraceRef = useRef<ThoughtEvent[]>([]);
  const toolCallTraceRef = useRef<ToolCallEvent[]>([]);
  const toolLifecycleRef = useRef<ToolLifecycleEvent[]>([]);
  const toolResultsRef = useRef<ToolResult[]>([]);
  const pendingApprovalsRef = useRef<ToolApprovalEvent[]>([]);
  const streamModesRef = useRef<StreamMode[]>([]);
  const turnMetadataRef = useRef<TurnMetadata | null>(null);
  const continuationHintRef = useRef<"auto_continue" | "await_user" | "compacting" | null>(null);

  const {
    conversations,
    activeConversationId,
    activeConversation,
    createConversation,
    updateConversation,
    addMessage,
    appendToMessage,
    setMessageThoughtTrace,
    setMessageToolCalls,
    setMessageToolLifecycle,
    setMessageToolResults,
    setMessageTurnMetadata,
    setMessagePendingApprovals,
  } = useChatStore();

  const model = useSettingsStore((s) => s.model);
  const skill = useSettingsStore((s) => s.skill);
  const style = useSettingsStore((s) => s.style);
  const researchMode = useSettingsStore((s) => s.researchMode);
  const ultraplanMode = useSettingsStore((s) => s.ultraplanMode);
  const ultrathinkMode = useSettingsStore((s) => s.ultrathinkMode);

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

      // Show compacting indicator
      setStreamMode("compacting");
      setStatusMessage("Compacting context...");
      setIsStreaming(true);

      try {
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
      } finally {
        setStreamMode(null);
        setStatusMessage(null);
        setIsStreaming(false);
      }
    },
    [activeConversationId, addMessage, model, updateConversation]
  );

  const sendMessage = useCallback(
    async (content: string, attachments?: FileAttachment[]) => {
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
      const turnId = genId();

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
      setStreamMode(null);
      thoughtTraceRef.current = [];
      toolCallTraceRef.current = [];
      toolLifecycleRef.current = [];
      toolResultsRef.current = [];
      pendingApprovalsRef.current = [];
      streamModesRef.current = [];
      turnMetadataRef.current = null;
      continuationHintRef.current = null;
      
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of sendChatStream(apiMessages, model, controller.signal, convId, memoryEnabled, skill, style, researchMode, attachments, ultraplanMode, ultrathinkMode, options?.devMode)) {
          if (event.type === "status") {
            setStatusMessage(event.content || null);
          } else if (event.type === "thought") {
            const thoughtContent = event.content || "";
            const thought: ThoughtEvent = { content: thoughtContent, timestamp: Date.now() };
            thoughtTraceRef.current = [...thoughtTraceRef.current, thought];
            setLatestThought(thoughtContent);
          } else if (event.type === "plan") {
            // Plan mode: stream plan content as visible message text
            setStatusMessage(null);
            appendToMessage(convId!, assistantId, event.content || "");
          } else if (event.type === "tool_call") {
            // Legacy tool call format
            const toolCall: ToolCallEvent = {
              tool_name: event.tool_name || "tool",
              tool_input: event.tool_input,
              tool_call_id: event.tool_call_id,
              content: event.content || "",
              timestamp: Date.now(),
            };
            toolCallTraceRef.current = [...toolCallTraceRef.current, toolCall];
          } else if (event.type === "tool_start") {
            const lifecycle: ToolLifecycleEvent = {
              tool_call_id: event.tool_call_id || "",
              tool_name: event.tool_name || "tool",
              state: event.tool_state || "queued",
              input: event.tool_input,
              timestamp: Date.now(),
            };
            toolLifecycleRef.current = [...toolLifecycleRef.current, lifecycle];
          } else if (event.type === "tool_progress") {
            const lifecycle: ToolLifecycleEvent = {
              tool_call_id: event.tool_call_id || "",
              tool_name: event.tool_name || "tool",
              state: event.tool_state || "executing",
              progress: event.tool_progress || 0,
              output: event.content,
              timestamp: Date.now(),
            };
            toolLifecycleRef.current = [...toolLifecycleRef.current, lifecycle];
          } else if (event.type === "tool_result") {
            const result: ToolResult = {
              tool_call_id: event.tool_call_id || "",
              tool_name: event.tool_name || "tool",
              success: (event.tool_state || "completed") === "completed",
              output: event.tool_output || event.content || "",
              artifacts: event.artifacts,
              timestamp: Date.now(),
            };
            toolResultsRef.current = [...toolResultsRef.current, result];
            // Editor sync callback for write_file results
            if (options?.onToolResult && event.tool_name) {
              options.onToolResult(
                event.tool_name,
                (event.tool_input as Record<string, unknown>) || {},
                event.tool_output || event.content || "",
              );
            }
            // Remove corresponding pending approval (if it was deferred to here)
            const resolvedId = event.tool_call_id;
            if (resolvedId) {
              pendingApprovalsRef.current = pendingApprovalsRef.current.filter(
                (a) => a.tool_call_id !== resolvedId
              );
              setMessagePendingApprovals(convId!, assistantId, pendingApprovalsRef.current);
            }
          } else if (event.type === "tool_approval_needed") {
            // Live-update the message with new pending approval so the UI can
            // show the Approve/Deny card immediately while streaming is paused.
            const approval = {
              tool_call_id: event.tool_call_id || "",
              tool_name: event.tool_name || "tool",
              tool_input: event.tool_input,
              timestamp: Date.now(),
            } satisfies ToolApprovalEvent;
            pendingApprovalsRef.current = [...pendingApprovalsRef.current, approval];
            setMessagePendingApprovals(convId!, assistantId, pendingApprovalsRef.current);
          } else if (event.type === "stream_mode") {
            const mode = event.streamMode || "responding";
            setStreamMode(mode);
            if (!streamModesRef.current.includes(mode)) {
              streamModesRef.current = [...streamModesRef.current, mode];
            }
          } else if (event.type === "turn_metadata") {
            const incoming = event.turnMetadata;
            if (incoming) {
              // Snapshot previous metadata before overwriting (breaks TS circular ref)
              const snap = JSON.parse(JSON.stringify(turnMetadataRef.current ?? {})) as Partial<TurnMetadata>;
              turnMetadataRef.current = {
                turnId: incoming.turnId || event.turnId || snap.turnId || turnId,
                agentName: incoming.agentName || snap.agentName,
                streamModes: streamModesRef.current,
                toolsInvoked: incoming.toolsInvoked || snap.toolsInvoked || [],
                continuable: incoming.continuable !== undefined ? incoming.continuable !== false : (snap.continuable ?? true),
                inContextTokens: incoming.inContextTokens ?? snap.inContextTokens,
                resumeToken: incoming.resumeToken || snap.resumeToken,
                traceId: incoming.traceId || snap.traceId,
              };
            }
          } else if (event.type === "continuation") {
            continuationHintRef.current = event.continuationHint || "await_user";
          } else if (event.type === "turn_boundary") {
            // Marker event for turn boundaries; no-op for now.
          } else if (event.type === "log") {
            // Internal pipeline diagnostics (security scan results, routing
            // decisions, etc.).  Route into thought trace so they appear in
            // the expandable thought panel, NOT as visible message content.
            const logContent = event.content || "";
            const thought: ThoughtEvent = { content: logContent, timestamp: Date.now() };
            thoughtTraceRef.current = [...thoughtTraceRef.current, thought];
            setLatestThought(logContent);
          } else if (event.type === "error") {
            appendToMessage(convId!, assistantId, `\n\n*Error: ${event.content || "Stream error"}*`);
          } else {
            // Clear status once real content arrives
            setStatusMessage(null);
            appendToMessage(convId!, assistantId, event.content || "");
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          // User cancelled
        } else {
          appendToMessage(convId!, assistantId, "\n\n*Error: Connection failed.*");
        }
      } finally {
        // Persist collected metadata to store
        if (thoughtTraceRef.current.length > 0) {
          setMessageThoughtTrace(convId!, assistantId, thoughtTraceRef.current);
        }
        if (toolCallTraceRef.current.length > 0) {
          setMessageToolCalls(convId!, assistantId, toolCallTraceRef.current);
        }
        if (toolLifecycleRef.current.length > 0 && setMessageToolLifecycle) {
          setMessageToolLifecycle(convId!, assistantId, toolLifecycleRef.current);
        }
        if (toolResultsRef.current.length > 0 && setMessageToolResults) {
          setMessageToolResults(convId!, assistantId, toolResultsRef.current);
        }
        if (turnMetadataRef.current && setMessageTurnMetadata) {
          setMessageTurnMetadata(convId!, assistantId, turnMetadataRef.current);
        }
        // Clear any remaining pending approvals (stream ended — no more waiting)
        if (pendingApprovalsRef.current.length > 0) {
          setMessagePendingApprovals(convId!, assistantId, []);
          pendingApprovalsRef.current = [];
        }

        setIsStreaming(false);
        setStatusMessage(null);
        setLatestThought(null);
        setStreamMode(null);
        thoughtTraceRef.current = [];
        toolCallTraceRef.current = [];
        toolLifecycleRef.current = [];
        toolResultsRef.current = [];
        streamModesRef.current = [];
        turnMetadataRef.current = null;
        continuationHintRef.current = null;
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
      skill,
      style,
      researchMode,
      ultraplanMode,
      ultrathinkMode,
      isStreaming,
      setMessageThoughtTrace,
      setMessageToolCalls,
      setMessageToolLifecycle,
      setMessageToolResults,
      setMessageTurnMetadata,
      setMessagePendingApprovals,
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
    streamMode,
    tokenUsage,
    sendMessage,
    compactConversation,
    stopGeneration,
  };
}
