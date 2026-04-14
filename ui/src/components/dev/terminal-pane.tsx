"use client";

import { useEffect, useRef } from "react";
import { Terminal as TerminalIcon } from "lucide-react";

export function TerminalPane() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<import("@xterm/xterm").Terminal | null>(null);
  const fitAddonRef = useRef<import("@xterm/addon-fit").FitAddon | null>(null);

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

      // Welcome message
      term.writeln("\x1b[36mâ•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—\x1b[0m");
      term.writeln("\x1b[36mâ•‘\x1b[0m   Hive Mind â€” Dev Terminal       \x1b[36mâ•‘\x1b[0m");
      term.writeln("\x1b[36mâ•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•\x1b[0m");
      term.writeln("");

      // Local echo â€” for now, just echo input back as a scratch terminal
      let line = "";
      term.write("\x1b[32m$ \x1b[0m");

      term.onData((data) => {
        if (data === "\r") {
          term.writeln("");
          if (line.trim()) {
            term.writeln(`\x1b[33mâ†’ local echo: ${line}\x1b[0m`);
          }
          line = "";
          term.write("\x1b[32m$ \x1b[0m");
        } else if (data === "\x7f") {
          // Backspace
          if (line.length > 0) {
            line = line.slice(0, -1);
            term.write("\b \b");
          }
        } else if (data >= " ") {
          line += data;
          term.write(data);
        }
      });
    }

    init();

    return () => {
      mounted = false;
      termRef.current?.dispose();
      termRef.current = null;
      fitAddonRef.current = null;
    };
  }, []);

  // Handle resize
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      fitAddonRef.current?.fit();
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
        <TerminalIcon size={13} />
        <span>Terminal</span>
        <span className="text-[var(--chat-muted)] ml-auto">local echo</span>
      </div>
      <div ref={containerRef} className="flex-1 px-1 py-1" />
    </div>
  );
}
