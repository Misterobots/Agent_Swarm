"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, Wifi, WifiOff, RotateCcw, Monitor } from "lucide-react";
import { useDesktop } from "@/lib/hooks/use-desktop";
import { useSettingsStore } from "@/lib/stores/settings-store";

// ---------------------------------------------------------------------------
// WebSocket helpers (remote server terminal — existing behaviour)
// ---------------------------------------------------------------------------
const WS_BASE = (() => {
  const gateway = process.env.NEXT_PUBLIC_GATEWAY_URL || "";
  if (gateway.startsWith("https://")) return gateway.replace("https://", "wss://");
  if (gateway.startsWith("http://"))  return gateway.replace("http://", "ws://");
  if (typeof window !== "undefined") {
    return (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
  }
  return "ws://localhost";
})();

function readUidCookie(): string | null {
  if (typeof document === "undefined") return null;
  const raw = document.cookie
    .split("; ")
    .find((c) => c.startsWith("authentik_uid="))
    ?.split("=")[1];
  return raw?.trim() || null;
}

type ConnState = "connecting" | "connected" | "disconnected" | "error";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
interface TerminalPaneProps {
  /** Session-scoped ID — prevents PTY collisions between tabs. */
  sessionId?: string;
}

export function TerminalPane({ sessionId = "default" }: TerminalPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef      = useRef<import("@xterm/xterm").Terminal | null>(null);
  const fitAddonRef  = useRef<import("@xterm/addon-fit").FitAddon | null>(null);
  const wsRef        = useRef<WebSocket | null>(null);
  const ptyIdRef     = useRef<string>(`pty-${sessionId}-${Date.now()}`);

  const [connState, setConnState] = useState<ConnState>("connecting");
  const [uidMissing, setUidMissing] = useState(false);

  const { inDesktop, bridge } = useDesktop();
  const desktopLocalPath = useSettingsStore((s) => s.desktopLocalPath);

  // ---------------------------------------------------------------------------
  // WebSocket backend (remote server)
  // ---------------------------------------------------------------------------
  function connectWs(term: import("@xterm/xterm").Terminal) {
    const uid = readUidCookie();
    if (!uid) { setUidMissing(true); return; }

    wsRef.current?.close();
    setConnState("connecting");

    const ws = new WebSocket(`${WS_BASE}/ws/terminal?uid=${encodeURIComponent(uid)}`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setConnState("connected");
      const dims = fitAddonRef.current?.proposeDimensions();
      if (dims) ws.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
    };
    ws.onmessage = (ev) => {
      term.write(
        ev.data instanceof ArrayBuffer
          ? new TextDecoder().decode(ev.data)
          : ev.data
      );
    };
    ws.onerror = () => setConnState("error");
    ws.onclose = () => {
      setConnState("disconnected");
      term.writeln("\r\n\x1b[33m[disconnected — click reconnect to restore session]\x1b[0m\r\n");
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(data));
    });
  }

  // ---------------------------------------------------------------------------
  // Native PTY backend (Memex Desktop via window.memex.pty)
  // ---------------------------------------------------------------------------
  async function connectPty(term: import("@xterm/xterm").Terminal) {
    if (!bridge) return;
    const id  = ptyIdRef.current;
    const cwd = desktopLocalPath || undefined;

    setConnState("connecting");
    try {
      await bridge.pty.create(id, cwd);

      const offData = bridge.pty.onData(id, (data) => term.write(data));
      const offExit = bridge.pty.onExit(id, (code) => {
        setConnState("disconnected");
        term.writeln(`\r\n\x1b[33m[process exited with code ${code}]\x1b[0m\r\n`);
      });

      term.onData((data) => bridge.pty.write(id, data));

      setConnState("connected");

      // Cleanup when terminal unmounts
      return () => { offData(); offExit(); bridge.pty.kill(id); };
    } catch (err) {
      setConnState("error");
      term.writeln(`\r\n\x1b[31m[PTY error: ${err}]\x1b[0m\r\n`);
    }
  }

  // ---------------------------------------------------------------------------
  // Init xterm + choose backend
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || termRef.current) return;
    let mounted = true;
    let ptyCleanup: (() => void) | undefined;

    (async () => {
      const { Terminal }     = await import("@xterm/xterm");
      const { FitAddon }     = await import("@xterm/addon-fit");
      const { WebLinksAddon }= await import("@xterm/addon-web-links");

      if (!mounted || !containerRef.current) return;

      const fitAddon = new FitAddon();
      const term = new Terminal({
        cursorBlink: true,
        cursorStyle: "bar",
        fontSize: 13,
        lineHeight: 1.4,
        fontFamily: "'Cascadia Code', 'Fira Code', 'SF Mono', Consolas, monospace",
        scrollback: 5000,
        theme: {
          background:          "#0d1117",
          foreground:          "#e6edf3",
          cursor:              inDesktop ? "#d97757" : "#22d3ee",
          cursorAccent:        "#0d1117",
          selectionBackground: inDesktop ? "rgba(217,119,87,0.3)" : "rgba(34,211,238,0.2)",
          black:    "#1c2128", brightBlack:    "#6e7681",
          red:      "#ff7b72", brightRed:      "#ffa198",
          green:    "#3fb950", brightGreen:    "#56d364",
          yellow:   "#d29922", brightYellow:   "#e3b341",
          blue:     "#58a6ff", brightBlue:     "#79c0ff",
          magenta:  "#bc8cff", brightMagenta:  "#d2a8ff",
          cyan:     "#39c5cf", brightCyan:     "#56d4dd",
          white:    "#b1bac4", brightWhite:    "#f0f6fc",
        },
      });

      term.loadAddon(fitAddon);
      term.loadAddon(new WebLinksAddon());
      term.open(containerRef.current);
      fitAddon.fit();

      termRef.current    = term;
      fitAddonRef.current = fitAddon;

      if (inDesktop) {
        term.writeln("\x1b[90m[Memex Desktop — local shell]\x1b[0m\r\n");
        ptyCleanup = await connectPty(term) ?? undefined;
      } else {
        connectWs(term);
      }
    })();

    return () => {
      mounted = false;
      wsRef.current?.close();
      ptyCleanup?.();
      termRef.current?.dispose();
      termRef.current = fitAddonRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inDesktop]);

  // Resize observer — notify whichever backend is active
  useEffect(() => {
    const ro = new ResizeObserver(() => {
      fitAddonRef.current?.fit();
      const dims = fitAddonRef.current?.proposeDimensions();
      if (!dims) return;
      if (inDesktop && bridge) {
        bridge.pty.resize(ptyIdRef.current, dims.cols, dims.rows);
      } else if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
      }
    });
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [inDesktop, bridge]);

  function handleReconnect() {
    const term = termRef.current;
    if (!term) return;
    term.writeln("\r\n\x1b[36m[reconnecting...]\x1b[0m\r\n");
    if (inDesktop) {
      // New PTY ID on reconnect
      ptyIdRef.current = `pty-${sessionId}-${Date.now()}`;
      connectPty(term);
    } else {
      connectWs(term);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  const statusDot =
    connState === "connected"    ? <span className="w-1.5 h-1.5 rounded-full bg-green-400" /> :
    connState === "connecting"   ? <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" /> :
                                   <span className="w-1.5 h-1.5 rounded-full bg-red-400" />;

  if (uidMissing && !inDesktop) {
    return (
      <div className="flex flex-col h-full bg-[var(--chat-bg)]">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
          <TerminalIcon size={13} /><span>Terminal</span>
        </div>
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--chat-muted)] px-6 text-center">
          Session identity not available — please reload.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0d1117]">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)] flex-shrink-0">
        {inDesktop
          ? <Monitor size={12} className="text-[var(--chat-accent,#d97757)]" />
          : <TerminalIcon size={12} />
        }
        <span>{inDesktop ? "Local shell" : "Terminal"}</span>
        {inDesktop && desktopLocalPath && (
          <span className="text-[var(--chat-muted)] opacity-60 truncate max-w-[200px]" title={desktopLocalPath}>
            {desktopLocalPath.split(/[/\\]/).slice(-2).join("/")}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {statusDot}
          <span className="capitalize">{connState}</span>
          {(connState === "disconnected" || connState === "error") && (
            <button
              onClick={handleReconnect}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[var(--chat-surface)] hover:bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            >
              <RotateCcw size={11} /> Reconnect
            </button>
          )}
        </div>
      </div>

      {/* xterm container */}
      <div ref={containerRef} className="flex-1 min-h-0 px-1 py-1 overflow-hidden" />
    </div>
  );
}
