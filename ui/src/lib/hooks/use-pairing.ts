"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const API = "/api/backend/api/v1/pairing";

export type PairingRole   = "host" | "guest";
export type PairingStatus = "idle" | "waiting" | "connected" | "error";

export interface PairingState {
  status:   PairingStatus;
  role:     PairingRole | null;
  code:     string | null;
  peerName: string | null;
  error:    string | null;
}

export interface PairingActions {
  host:       (displayName?: string) => Promise<void>;
  join:       (code: string, displayName?: string) => Promise<void>;
  disconnect: () => void;
  send:       (msg: Record<string, unknown>) => void;
  onMessage:  (cb: (msg: Record<string, unknown>) => void) => () => void;
}

const MEMEX_URL =
  typeof window !== "undefined" ? window.location.origin : "";

export function usePairing(): [PairingState, PairingActions] {
  const [state, setState] = useState<PairingState>({
    status: "idle", role: null, code: null, peerName: null, error: null,
  });

  const wsRef       = useRef<WebSocket | null>(null);
  const tokenRef    = useRef<string | null>(null);
  const listenersRef = useRef<Set<(msg: Record<string, unknown>) => void>>(new Set());

  const cleanup = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    if (tokenRef.current) {
      fetch(`${API}/leave/${tokenRef.current}`, { method: "DELETE" }).catch(() => {});
      tokenRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const connectWs = useCallback((token: string) => {
    const wsBase = MEMEX_URL.replace(/^https/, "wss").replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/api/backend/api/v1/pairing/ws/${token}`);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as Record<string, unknown>;
        if (msg.type === "peer_joined") {
          setState((s) => ({ ...s, status: "connected" }));
        } else if (msg.type === "peer_left") {
          setState((s) => ({ ...s, status: "waiting", peerName: null }));
        } else {
          listenersRef.current.forEach((cb) => cb(msg));
        }
      } catch {}
    };

    ws.onerror = () => setState((s) => ({ ...s, status: "error", error: "WebSocket error" }));
    ws.onclose = () => setState((s) =>
      s.status === "connected" ? { ...s, status: "waiting" } : s
    );
  }, []);

  const host = useCallback(async (displayName = "Memex Desktop") => {
    cleanup();
    try {
      const res = await fetch(`${API}/create`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ display_name: displayName, memex_url: MEMEX_URL }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json() as { code: string; token: string };
      tokenRef.current = data.token;
      setState({ status: "waiting", role: "host", code: data.code, peerName: null, error: null });
      connectWs(data.token);
    } catch (e: unknown) {
      setState({ status: "error", role: null, code: null, peerName: null, error: String(e) });
    }
  }, [cleanup, connectWs]);

  const join = useCallback(async (code: string, displayName = "Memex Desktop") => {
    cleanup();
    try {
      const res = await fetch(`${API}/join/${code.toUpperCase()}`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ display_name: displayName }),
      });
      if (!res.ok) throw new Error(res.status === 404 ? "Code not found" : `${res.status}`);
      const data = await res.json() as { token: string; host_info: { display_name: string } };
      tokenRef.current = data.token;
      setState({
        status: "connected", role: "guest", code: code.toUpperCase(),
        peerName: data.host_info.display_name, error: null,
      });
      connectWs(data.token);
    } catch (e: unknown) {
      setState({ status: "error", role: null, code: null, peerName: null, error: String(e) });
    }
  }, [cleanup, connectWs]);

  const disconnect = useCallback(() => {
    cleanup();
    setState({ status: "idle", role: null, code: null, peerName: null, error: null });
  }, [cleanup]);

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const onMessage = useCallback((cb: (msg: Record<string, unknown>) => void) => {
    listenersRef.current.add(cb);
    return () => listenersRef.current.delete(cb);
  }, []);

  return [state, { host, join, disconnect, send, onMessage }];
}
