"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, Plus, X, Wifi, WifiOff, RotateCcw } from "lucide-react";
import { useDevPanelStore } from "@/lib/stores/dev-panel-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useDevProjectStore } from "@/lib/stores/dev-project-store";
import { getXtermTheme } from "./dev-theme-map";

const WS_BASE = (() => {
  const gateway = process.env.NEXT_PUBLIC_GATEWAY_URL || "";
  if (gateway.startsWith("https://")) return gateway.replace("https://", "wss://");
  if (gateway.startsWith("http://")) return gateway.replace("http://", "ws://");
  if (typeof window !== "undefined") return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
  return "ws://localhost";
})();

type ConnState = "connecting" | "connected" | "disconnected" | "error";
interface TerminalTab { id: string; title: string; connState: ConnState; }
const MAX_TABS = 5;

export function TabbedTerminal() {
  const { activeTerminalId, addTerminalTab, removeTerminalTab, setActiveTerminal } = useDevPanelStore();
  const containerRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const terminalsRef = useRef<Map<string, import("@xterm/xterm").Terminal>>(new Map());
  const socketsRef = useRef<Map<string, WebSocket>>(new Map());
  const fitAddons = useRef<Map<string, import("@xterm/addon-fit").FitAddon>>(new Map());
  const resizeObservers = useRef<Map<string, ResizeObserver>>(new Map());
  const tabSequence = useRef(0);
  const { theme: themeId, themeMode } = useSettingsStore();
  const [tabs, setTabs] = useState<TerminalTab[]>([]);

  useEffect(() => {
    const xtermTheme = getXtermTheme(themeId, themeMode === "light");
    terminalsRef.current.forEach((term) => { term.options.theme = xtermTheme; });
  }, [themeId, themeMode]);

  useEffect(() => () => {
    resizeObservers.current.forEach((observer) => observer.disconnect());
    socketsRef.current.forEach((socket) => socket.close());
    terminalsRef.current.forEach((term) => term.dispose());
    resizeObservers.current.clear(); socketsRef.current.clear(); terminalsRef.current.clear(); fitAddons.current.clear();
  }, []);

  function getUid() {
    if (typeof document === "undefined") return "dev";
    return document.cookie.split("; ").find((cookie) => cookie.startsWith("authentik_uid="))?.split("=")[1] ?? "dev";
  }

  function setConnectionState(tabId: string, connState: ConnState) {
    setTabs((previous) => previous.map((tab) => tab.id === tabId ? { ...tab, connState } : tab));
  }

  function sendResize(tabId: string) {
    const socket = socketsRef.current.get(tabId);
    const dimensions = fitAddons.current.get(tabId)?.proposeDimensions();
    if (socket?.readyState === WebSocket.OPEN && dimensions) socket.send(JSON.stringify({ type: "resize", cols: dimensions.cols, rows: dimensions.rows }));
  }

  function connectWs(tabId: string) {
    const term = terminalsRef.current.get(tabId);
    if (!term) return;
    socketsRef.current.get(tabId)?.close();
    setConnectionState(tabId, "connecting");
    const params = new URLSearchParams({ uid: getUid(), session: tabId });
    const projectId = useDevProjectStore.getState().currentProjectId;
    if (projectId) params.set("projectId", projectId);
    const socket = new WebSocket(`${WS_BASE}/ws/terminal?${params.toString()}`);
    socket.binaryType = "arraybuffer";
    socketsRef.current.set(tabId, socket);
    socket.onopen = () => {
      if (socketsRef.current.get(tabId) !== socket) return;
      setConnectionState(tabId, "connected"); sendResize(tabId);
    };
    socket.onmessage = (event) => {
      if (socketsRef.current.get(tabId) !== socket) return;
      const currentTerm = terminalsRef.current.get(tabId);
      if (currentTerm) currentTerm.write(event.data instanceof ArrayBuffer ? new TextDecoder().decode(event.data) : event.data);
    };
    socket.onerror = () => { if (socketsRef.current.get(tabId) === socket) setConnectionState(tabId, "error"); };
    socket.onclose = () => {
      if (socketsRef.current.get(tabId) !== socket) return;
      socketsRef.current.delete(tabId); setConnectionState(tabId, "disconnected");
      terminalsRef.current.get(tabId)?.writeln("\r\n\x1b[33m[disconnected — click reconnect]\x1b[0m\r\n");
    };
  }

  function createTab() {
    if (tabs.length >= MAX_TABS) { alert(`Maximum ${MAX_TABS} terminals allowed`); return; }
    tabSequence.current += 1;
    const id = `term-${Date.now()}-${tabSequence.current}`;
    const title = `Terminal ${tabs.length + 1}`;
    setTabs((previous) => [...previous, { id, title, connState: "connecting" }]);
    addTerminalTab(id, title); setActiveTerminal(id);
  }

  function disposeTab(tabId: string) {
    resizeObservers.current.get(tabId)?.disconnect(); resizeObservers.current.delete(tabId);
    socketsRef.current.get(tabId)?.close(); socketsRef.current.delete(tabId);
    terminalsRef.current.get(tabId)?.dispose(); terminalsRef.current.delete(tabId);
    fitAddons.current.delete(tabId); containerRefs.current.delete(tabId);
  }

  function closeTab(tabId: string) {
    const remaining = tabs.filter((tab) => tab.id !== tabId);
    disposeTab(tabId); setTabs(remaining);
    if (tabId === activeTerminalId) setActiveTerminal(remaining[0]?.id || "");
    removeTerminalTab(tabId);
  }

  function initTerminal(tabId: string, container: HTMLDivElement) {
    if (terminalsRef.current.has(tabId)) return;
    Promise.all([import("@xterm/xterm"), import("@xterm/addon-fit"), import("@xterm/addon-web-links")]).then(([{ Terminal }, { FitAddon }, { WebLinksAddon }]) => {
      // The tab may have closed while xterm's chunks loaded.
      if (containerRefs.current.get(tabId) !== container || terminalsRef.current.has(tabId)) return;
      const fitAddon = new FitAddon();
      const term = new Terminal({ cursorBlink: true, fontSize: 13, fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace", theme: getXtermTheme(useSettingsStore.getState().theme, useSettingsStore.getState().themeMode === "light") });
      term.loadAddon(fitAddon); term.loadAddon(new WebLinksAddon()); term.open(container); fitAddon.fit();
      terminalsRef.current.set(tabId, term); fitAddons.current.set(tabId, fitAddon);
      term.onData((data) => {
        const socket = socketsRef.current.get(tabId);
        if (socket?.readyState === WebSocket.OPEN) socket.send(new TextEncoder().encode(data));
      });
      const observer = new ResizeObserver(() => { fitAddon.fit(); sendResize(tabId); });
      observer.observe(container); resizeObservers.current.set(tabId, observer);
      connectWs(tabId);
    });
  }

  const activeTab = tabs.find((tab) => tab.id === activeTerminalId) || tabs[0];
  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="flex items-center border-b border-[var(--chat-border)] bg-[var(--chat-bg)]">
        <div className="flex flex-1 overflow-x-auto">
          {tabs.map((tab) => (
            <div key={tab.id} className={`group flex items-center gap-2 px-3 py-2 text-xs cursor-pointer transition-colors border-r border-[var(--chat-border)] ${tab.id === activeTerminalId ? "text-[var(--chat-accent)] bg-[var(--chat-bg)] border-b-2 border-[var(--chat-accent)]" : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-hover)]"}`} onClick={() => setActiveTerminal(tab.id)}>
              <TerminalIcon size={14} /><span>{tab.title}</span>
              {tab.connState === "connected" && <Wifi size={12} className="text-emerald-500" />}
              {tab.connState === "disconnected" && <WifiOff size={12} className="text-amber-500" />}
              {tab.connState === "error" && <WifiOff size={12} className="text-red-500" />}
              {tabs.length > 1 && <button onClick={(event) => { event.stopPropagation(); closeTab(tab.id); }} className="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity" aria-label={`Close ${tab.title}`}><X size={14} /></button>}
            </div>
          ))}
        </div>
        {tabs.length < MAX_TABS && <button onClick={createTab} className="px-3 py-2 text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors" title="New terminal" aria-label="New terminal"><Plus size={16} /></button>}
        {activeTab && activeTab.connState !== "connected" && <button onClick={() => connectWs(activeTab.id)} className="px-3 py-2 text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors" title="Reconnect" aria-label="Reconnect terminal"><RotateCcw size={16} /></button>}
      </div>
      <div className="flex-1 relative">
        {tabs.length === 0 ? <div className="flex flex-col items-center justify-center h-full text-[var(--chat-muted)]"><TerminalIcon size={48} className="mb-4 opacity-50" /><p className="text-sm mb-4">No terminal sessions</p><button onClick={createTab} className="px-4 py-2 bg-[var(--chat-accent)] text-white rounded hover:opacity-90 transition-opacity flex items-center gap-2"><Plus size={16} /> New Terminal</button></div> : tabs.map((tab) => (
          <div key={tab.id} ref={(element) => { if (element) { containerRefs.current.set(tab.id, element); initTerminal(tab.id, element); } }} className={`absolute inset-0 ${tab.id === activeTerminalId ? "block" : "hidden"}`} />
        ))}
      </div>
    </div>
  );
}
