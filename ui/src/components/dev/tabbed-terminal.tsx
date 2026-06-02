"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, Plus, X, Wifi, WifiOff, RotateCcw } from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { getXtermTheme } from "./dev-theme-map";

const WS_BASE = (() => {
  const gateway = process.env.NEXT_PUBLIC_GATEWAY_URL || "";
  if (gateway.startsWith("https://")) return gateway.replace("https://", "wss://");
  if (gateway.startsWith("http://")) return gateway.replace("http://", "ws://");
  if (typeof window !== "undefined") {
    return (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
  }
  return "ws://localhost";
})();

type ConnState = "connecting" | "connected" | "disconnected" | "error";

interface TerminalTab {
  id: string;
  title: string;
  term: import("@xterm/xterm").Terminal | null;
  ws: WebSocket | null;
  connState: ConnState;
}

const MAX_TABS = 5;

export function TabbedTerminal() {
  const { terminalTabs, activeTerminalId, addTerminalTab, removeTerminalTab, setActiveTerminal } = useDevStore();
  const containerRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const fitAddons = useRef<Map<string, import("@xterm/addon-fit").FitAddon>>(new Map());
  const { theme: themeId, themeMode } = useSettingsStore();
  const isLight = themeMode === "light";

  const [tabs, setTabs] = useState<TerminalTab[]>([]);

  // Update all terminal themes when Memex theme changes
  useEffect(() => {
    const xtermTheme = getXtermTheme(themeId, isLight);
    setTabs((prev) =>
      prev.map((t) => {
        if (t.term) {
          t.term.options.theme = xtermTheme;
        }
        return t;
      })
    );
  }, [themeId, isLight]);

  function getUid(): string {
    if (typeof document === "undefined") return "dev";
    return document.cookie
      .split("; ")
      .find((c) => c.startsWith("authentik_uid="))
      ?.split("=")[1] ?? "dev";
  }

  function createTab() {
    if (tabs.length >= MAX_TABS) {
      alert(`Maximum ${MAX_TABS} terminals allowed`);
      return;
    }
    
    const newId = `term-${Date.now()}`;
    const newTab: TerminalTab = {
      id: newId,
      title: `Terminal ${tabs.length + 1}`,
      term: null,
      ws: null,
      connState: "connecting",
    };
    
    setTabs((prev) => [...prev, newTab]);
    addTerminalTab(newId, newTab.title);
    setActiveTerminal(newId);
  }

  function closeTab(tabId: string) {
    const tab = tabs.find((t) => t.id === tabId);
    if (tab) {
      tab.ws?.close();
      tab.term?.dispose();
    }
    
    setTabs((prev) => {
      const filtered = prev.filter((t) => t.id !== tabId);
      // If closing active tab, switch to first remaining tab
      if (tabId === activeTerminalId && filtered.length > 0) {
        setActiveTerminal(filtered[0].id);
      }
      return filtered;
    });
    
    removeTerminalTab(tabId);
    containerRefs.current.delete(tabId);
    fitAddons.current.delete(tabId);
  }

  function connectWs(tab: TerminalTab) {
    if (!tab.term) return;
    
    if (tab.ws) {
      tab.ws.close();
      tab.ws = null;
    }
    
    const wsUrl = `${WS_BASE}/ws/terminal?uid=${encodeURIComponent(getUid())}&session=${encodeURIComponent(tab.id)}`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    tab.ws = ws;

    ws.onopen = () => {
      setTabs((prev) =>
        prev.map((t) => (t.id === tab.id ? { ...t, connState: "connected" } : t))
      );
      // Send initial dimensions
      const fitAddon = fitAddons.current.get(tab.id);
      const dims = fitAddon?.proposeDimensions();
      if (dims) {
        ws.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
      }
    };

    ws.onmessage = (ev) => {
      if (!tab.term) return;
      if (ev.data instanceof ArrayBuffer) {
        const decoder = new TextDecoder();
        tab.term.write(decoder.decode(ev.data));
      } else {
        tab.term.write(ev.data);
      }
    };

    ws.onerror = () => {
      setTabs((prev) =>
        prev.map((t) => (t.id === tab.id ? { ...t, connState: "error" } : t))
      );
    };

    ws.onclose = () => {
      setTabs((prev) =>
        prev.map((t) => (t.id === tab.id ? { ...t, connState: "disconnected" } : t))
      );
      tab.term?.writeln("\r\n\x1b[33m[disconnected — click reconnect]\x1b[0m\r\n");
    };

    // Forward terminal input → WebSocket
    tab.term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });
  }

  function initTerminal(tabId: string, container: HTMLDivElement) {
    const tab = tabs.find((t) => t.id === tabId);
    if (!tab || tab.term) return;

    import("@xterm/xterm").then(({ Terminal }) => {
      import("@xterm/addon-fit").then(({ FitAddon }) => {
        import("@xterm/addon-web-links").then(({ WebLinksAddon }) => {
          const fitAddon = new FitAddon();
          // Read current theme at construction time; the theme-change effect
          // updates existing terminals when the Memex theme changes.
          const currentThemeId = useSettingsStore.getState().theme;
          const currentIsLight = useSettingsStore.getState().themeMode === "light";
          const term = new Terminal({
            cursorBlink: true,
            fontSize: 13,
            fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
            theme: getXtermTheme(currentThemeId, currentIsLight),
          });

          term.loadAddon(fitAddon);
          term.loadAddon(new WebLinksAddon());
          term.open(container);
          fitAddon.fit();

          fitAddons.current.set(tabId, fitAddon);
          
          setTabs((prev) =>
            prev.map((t) => (t.id === tabId ? { ...t, term } : t))
          );

          // Connect WebSocket
          connectWs({ ...tab, term });

          // Resize observer
          const resizeObs = new ResizeObserver(() => {
            fitAddon.fit();
            const dims = fitAddon.proposeDimensions();
            if (dims && tab.ws?.readyState === WebSocket.OPEN) {
              tab.ws.send(JSON.stringify({ type: "resize", cols: dims.cols, rows: dims.rows }));
            }
          });
          resizeObs.observe(container);

          return () => {
            resizeObs.disconnect();
            term.dispose();
          };
        });
      });
    });
  }

  // Don't auto-create terminal tabs - let user create them explicitly
  useEffect(() => {
    // Intentionally empty - no auto-creation
  }, []);

  const activeTab = tabs.find((t) => t.id === activeTerminalId) || tabs[0];

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      {/* Tab Bar */}
      <div className="flex items-center border-b border-[var(--chat-border)] bg-[var(--chat-bg)]">
        <div className="flex flex-1 overflow-x-auto">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`group flex items-center gap-2 px-3 py-2 text-xs cursor-pointer transition-colors border-r border-[var(--chat-border)] ${
                tab.id === activeTerminalId
                  ? "text-[var(--chat-accent)] bg-[var(--chat-bg)] border-b-2 border-[var(--chat-accent)]"
                  : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-hover)]"
              }`}
              onClick={() => setActiveTerminal(tab.id)}
            >
              <TerminalIcon size={14} />
              <span>{tab.title}</span>
              
              {/* Connection status */}
              {tab.connState === "connected" && <Wifi size={12} className="text-green-500" />}
              {tab.connState === "disconnected" && <WifiOff size={12} className="text-yellow-500" />}
              {tab.connState === "error" && <WifiOff size={12} className="text-red-500" />}
              
              {/* Close button */}
              {tabs.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(tab.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
        
        {/* Add button */}
        {tabs.length < MAX_TABS && (
          <button
            onClick={createTab}
            className="px-3 py-2 text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors"
            title="New terminal"
          >
            <Plus size={16} />
          </button>
        )}
        
        {/* Reconnect button for active tab */}
        {activeTab && activeTab.connState !== "connected" && (
          <button
            onClick={() => connectWs(activeTab)}
            className="px-3 py-2 text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors"
            title="Reconnect"
          >
            <RotateCcw size={16} />
          </button>
        )}
      </div>

      {/* Terminal containers */}
      <div className="flex-1 relative">
        {tabs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--chat-muted)]">
            <TerminalIcon size={48} className="mb-4 opacity-50" />
            <p className="text-sm mb-4">No terminal sessions</p>
            <button
              onClick={createTab}
              className="px-4 py-2 bg-[var(--chat-accent)] text-white rounded hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <Plus size={16} />
              New Terminal
            </button>
          </div>
        ) : (
          tabs.map((tab) => (
            <div
              key={tab.id}
              ref={(el) => {
                if (el) {
                  containerRefs.current.set(tab.id, el);
                  if (!tab.term) {
                    initTerminal(tab.id, el);
                  }
                }
              }}
              className={`absolute inset-0 ${tab.id === activeTerminalId ? "block" : "hidden"}`}
            />
          ))
        )}
      </div>
    </div>
  );
}
