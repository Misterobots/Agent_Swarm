"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, Wifi, WifiOff, RotateCcw } from "lucide-react";

const WS_BASE = (() => {
  const gateway = process.env.NEXT_PUBLIC_GATEWAY_URL || "";
  // Convert http(s):// â†’ ws(s)://; fall back to relative path via same host
  if (gateway.startsWith("https://")) return gateway.replace("https://", "wss://");
  if (gateway.startsWith("http://")) return gateway.replace("http://", "ws://");
  // Relative: use current page's host
  if (typeof window !== "undefined") {
    return (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
  }
  return "ws://localhost";
})();

type ConnState = "connecting" | "connected" | "disconnected" | "error";

export function TerminalPane() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<import("@xterm/xterm").Terminal | null>(null);
  const fitAddonRef = useRef<import("@xterm/addon-fit").FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connState, setConnState] = useState<ConnState>("connecting");

  function buildWsUrl(): string {
    // Pass uid as query param (browsers can't set custom WS headers)
    const uid = document.cookie
      .split("; ")
      .find((c) => c.startsWith("authentik_uid="))
      ?.split("=")[1] ?? "dev";
    return `${WS_BASE}/ws/terminal?uid=${encodeURIComponent(uid)}`;
  }

  function connectWs(term: import("@xterm/xterm").Terminal) {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnState("connecting");
    const ws = new WebSocket(buildWsUrl());
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setConnState("connected");
      // Send initial terminal dimensions
      const dims = fitAddonRef.current?.proposeDimensions();
      if (dims) {
        ws.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
      }
    };

    ws.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        const decoder = new TextDecoder();
        term.write(decoder.decode(ev.data));
      } else {
        term.write(ev.data);
      }
    };

    ws.onerror = () => setConnState("error");
    ws.onclose = () => {
      setConnState("disconnected");
      term.writeln("\r\n\x1b[33m[disconnected â€” click reconnect to restore session]\x1b[0m\r\n");
    };

    // Forward terminal input â†’ WebSocket
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });
  }

  useEffect(() => {
    if (!containerRef.current || termRef.current) return;

    let mounted = true;

    async function init() {
      const { Terminal } = await import("@xterm/xterm");
      const { FitAddon } = await import("@xterm/addon-fit");
      const { WebLinksAddon } = await import("@xterm/addon-web-links");

      if (!mounted || !containerRef.current) return;

      const fitAddon = new FitAddon();
      const term = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
        theme: {
          background: "#0a0a14",
          foreground: "#e4e4e7",
          cursor: "#22d3ee",
          selectionBackground: "#22d3ee33",
          black: "#18181b",
          red: "#f87171",
          green: "#4ade80",
          yellow: "#facc15",
          blue: "#60a5fa",
          magenta: "#c084fc",
          cyan: "#22d3ee",
          white: "#e4e4e7",
        },
        allowProposedApi: true,
      });

      term.loadAddon(fitAddon);
      term.loadAddon(new WebLinksAddon());
      term.open(containerRef.current);
      fitAddon.fit();

      termRef.current = term;
      fitAddonRef.current = fitAddon;

      connectWs(term);
    }

    init();

    return () => {
      mounted = false;
      wsRef.current?.close();
      wsRef.current = null;
      termRef.current?.dispose();
      termRef.current = null;
      fitAddonRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle resize â€” also notify backend
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      fitAddonRef.current?.fit();
      const dims = fitAddonRef.current?.proposeDimensions();
      if (dims && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
      }
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  function handleReconnect() {
    if (termRef.current) {
      termRef.current.writeln("\r\n\x1b[36m[reconnecting...]\x1b[0m\r\n");
      connectWs(termRef.current);
    }
  }

  const statusIcon =
    connState === "connected" ? (
      <Wifi size={12} className="text-green-400" />
    ) : connState === "connecting" ? (
      <Wifi size={12} className="text-yellow-400 animate-pulse" />
    ) : (
      <WifiOff size={12} className="text-red-400" />
    );

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
        <TerminalIcon size={13} />
        <span>Terminal</span>
        <div className="ml-auto flex items-center gap-2">
          {statusIcon}
          <span className="capitalize">{connState}</span>
          {(connState === "disconnected" || connState === "error") && (
            <button
              onClick={handleReconnect}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[var(--chat-surface)] hover:bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            >
              <RotateCcw size={11} />
              Reconnect
            </button>
          )}
        </div>
      </div>
      <div ref={containerRef} className="flex-1 px-1 py-1 overflow-hidden" />
    </div>
  );
}
