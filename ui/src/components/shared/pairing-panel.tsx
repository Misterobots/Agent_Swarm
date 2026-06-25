"use client";

import { useState, useEffect } from "react";
import { usePairing } from "@/lib/hooks/use-pairing";
import { useChatStore } from "@/lib/stores/chat-store";

interface Props {
  onClose: () => void;
}

export function PairingPanel({ onClose }: Props) {
  const [code, setCode] = useState("");
  const [state, actions] = usePairing();
  const appendToMessage = useChatStore((s) => s.appendToMessage);

  // Relay incoming peer messages as chat prefills or agent prompts
  useEffect(() => {
    const off = actions.onMessage((msg) => {
      if (msg.type === "chat:prefill" && typeof msg.text === "string") {
        window.dispatchEvent(new CustomEvent("chat:prefill", { detail: msg.text }));
      }
      if (msg.type === "agent:trace" && typeof msg.content === "string") {
        // Surface peer's agent trace in the current conversation
        const convId = useChatStore.getState().activeConversationId;
        const msgs   = useChatStore.getState().activeConversation()?.messages ?? [];
        const last   = msgs[msgs.length - 1];
        if (convId && last && last.role === "assistant") {
          appendToMessage(convId, last.id, `\n\n*[Peer]* ${msg.content}`);
        }
      }
    });
    return off;
  }, [actions, appendToMessage]);

  const statusColor: Record<string, string> = {
    idle:      "text-[var(--chat-muted)]",
    waiting:   "text-yellow-400",
    connected: "text-green-400",
    error:     "text-red-400",
  };

  return (
    <div className="flex flex-col gap-4 p-4 min-w-[300px]">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-[var(--chat-text)]">Remote pairing</h2>
        <button onClick={onClose} className="text-[var(--chat-muted)] hover:text-[var(--chat-text)] text-lg leading-none">×</button>
      </div>

      {/* Status */}
      <div className={`text-xs font-mono ${statusColor[state.status]}`}>
        {state.status === "idle"      && "Not connected"}
        {state.status === "waiting"   && (state.role === "host" ? `Waiting for guest — share code: ${state.code}` : "Connecting…")}
        {state.status === "connected" && `Connected${state.peerName ? ` with ${state.peerName}` : ""}`}
        {state.status === "error"     && `Error: ${state.error}`}
      </div>

      {state.status === "idle" || state.status === "error" ? (
        <>
          {/* Host */}
          <button
            onClick={() => actions.host()}
            className="px-3 py-2 text-sm rounded-lg border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/40 hover:text-[var(--chat-text)] text-[var(--chat-muted)] transition-colors text-left"
          >
            <div className="font-medium text-[var(--chat-text)]">Share my session</div>
            <div className="text-xs mt-0.5">Generate a code for someone to join</div>
          </button>

          {/* Join */}
          <div className="space-y-2">
            <label className="text-xs text-[var(--chat-muted)] font-medium">Join a session</label>
            <div className="flex gap-2">
              <input
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase().slice(0, 6))}
                onKeyDown={(e) => e.key === "Enter" && code.length === 6 && actions.join(code)}
                placeholder="XXXXXX"
                maxLength={6}
                className="flex-1 bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-lg px-3 py-2 text-sm font-mono text-[var(--chat-text)] placeholder-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]/50 uppercase tracking-widest"
              />
              <button
                onClick={() => code.length === 6 && actions.join(code)}
                disabled={code.length !== 6}
                className="px-3 py-2 text-sm bg-[var(--chat-accent)] text-canvas rounded-lg hover:opacity-80 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Join
              </button>
            </div>
          </div>
        </>
      ) : (
        <>
          {/* Pairing code display */}
          {state.code && state.status === "waiting" && state.role === "host" && (
            <div className="flex flex-col items-center gap-2 py-3">
              <div className="text-4xl font-mono font-bold tracking-[0.3em] text-[var(--chat-accent)]">
                {state.code}
              </div>
              <p className="text-xs text-[var(--chat-muted)] text-center">
                Share this code with another Memex Desktop user
              </p>
            </div>
          )}

          {/* Connected — relay controls */}
          {state.status === "connected" && (
            <div className="space-y-2">
              <button
                onClick={() => actions.send({ type: "chat:prefill", text: "Hello from paired session!" })}
                className="w-full px-3 py-2 text-xs rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/40 text-[var(--chat-muted)] hover:text-[var(--chat-text)] text-left"
              >
                Test — send hello to peer
              </button>
            </div>
          )}

          <button
            onClick={actions.disconnect}
            className="px-3 py-2 text-sm rounded-lg border border-red-700/40 text-red-400 hover:bg-red-950/20 transition-colors"
          >
            Disconnect
          </button>
        </>
      )}
    </div>
  );
}
