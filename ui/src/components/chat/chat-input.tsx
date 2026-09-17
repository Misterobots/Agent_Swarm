"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Square } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { canSelectModel } from "@/lib/utils/model-access";
import { ChatSettingsMenu } from "./chat-settings-menu";
import { IconButton } from "@/components/ui";
import { useVimInput } from "@/lib/hooks/use-vim-input";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, onStop, isStreaming, placeholder }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const model = useSettingsStore((s) => s.model);
  const setModel = useSettingsStore((s) => s.setModel);
  const vimMode = useSettingsStore((s) => s.vimMode);
  // vim hook initialized with a stable ref; actual handleSend assigned after its definition
  const vimHandleSendRef = useRef<() => void>(() => {});
  const vim = useVimInput(textareaRef as React.RefObject<HTMLTextAreaElement>, () => vimHandleSendRef.current());

  // Claude Code commands (local handling) + Memex workflow commands (passed to backend)
  const commands = [
    // Agent Flows
    { cmd: "/flow-blockout", label: "Blockout Flow", category: "Flow", description: "Rough, rapid first-pass draft of nonexistent structure (schemas, folder layouts, configs)." },
    { cmd: "/flow-batch-edit", label: "Batch Edit Flow", category: "Flow", description: "Apply one mechanical change across N existing files matching a predicate. Reversible." },
    { cmd: "/flow-audit", label: "Audit Flow", category: "Flow", description: "Read-only sweep checking a large set against explicit rules (dead links, broken exports). Never mutates." },
    { cmd: "/flow-scaffold", label: "Scaffold Flow", category: "Flow", description: "Generate boilerplate skeleton for one new unit (component, service, route) with empty logic." },
    { cmd: "/flow-variants", label: "Variants Flow", category: "Flow", description: "Generate N named derivatives from one parent template plus a parameter table." },
    { cmd: "/agent-flows", label: "Agent Flows Guide", category: "Flow", description: "Routing guide and 3-part selection gate for picking the right agent flow." },

    // Backend: Memex workflows
    { cmd: "/build", label: "Collective Build", category: "Workflow", description: "Multi-agent swarm coordination to plan, write, and verify code across files." },
    { cmd: "/swarm", label: "Swarm Mode", category: "Workflow", description: "Alias for Collective build: coordinate specialists to execute project tasks." },
    { cmd: "/plan", label: "Plan Mode", category: "Workflow", description: "Explicit planning and exploration phase with ultraplan before modifying files." },
    { cmd: "/workshop", label: "Product Workshop", category: "Workflow", description: "Two-phase discovery: interactive grill-me questions → Product Brief → pipeline actions." },
    { cmd: "/grill", label: "Grill Me", category: "Workflow", description: "Deep discovery interview to align on requirements and eliminate ambiguity." },
    { cmd: "/design", label: "Design Studio", category: "Workflow", description: "Generate self-contained UI/HTML mockups and Open Design projects." },
    { cmd: "/research", label: "Deep Research", category: "Workflow", description: "Deep web and documentation research with perspective synthesis." },
    { cmd: "/think", label: "Extended Thinking", category: "Workflow", description: "Extended step-by-step reasoning for difficult problems before responding." },
    { cmd: "/cad", label: "CAD Modeling", category: "Workflow", description: "Generate OpenSCAD 3D models with 2D preview renders and STL export." },

    // Local: chat & model management
    { cmd: "/compact", label: "Compact Context", category: "Utility", description: "Summarize earlier conversation turns to reclaim token budget." },
    { cmd: "/clear", label: "Clear Thread", category: "Utility", description: "Clear active conversation messages and reset thread state." },
    { cmd: "/model", label: "Model Info / Switch", category: "Utility", description: "Show active model and context window or switch model." },
    { cmd: "/memory", label: "MemPalace Memory", category: "Utility", description: "Inspect or search persistent long-term memory." },
    { cmd: "/help", label: "Help", category: "Utility", description: "List all available slash commands, workflows, and shortcuts." },
  ];
  const [slashIndex, setSlashIndex] = useState(0);
  const isSlash = input.startsWith("/") && !input.trimStart().includes(" ");
  const commandQuery = isSlash ? input.trimStart().slice(1).toLowerCase() : "";
  const matches = isSlash
    ? commands.filter((c) => c.cmd.slice(1).toLowerCase().startsWith(commandQuery) || c.label.toLowerCase().includes(commandQuery))
    : [];

  useEffect(() => {
    setSlashIndex(0);
  }, [commandQuery]);

  const executeSlash = useCallback(
    (raw: string): boolean => {
      const [cmd, ...rest] = raw.trim().split(/\s+/);
      const arg = rest.join(" ");

      if (cmd === "/clear") {
        if (activeConversationId) deleteConversation(activeConversationId);
        setInput("");
        return true;
      }
      if (cmd === "/model") {
        if (arg) {
          if (!canSelectModel(arg)) {
            onSend("That model is not available for chat.");
            setInput("");
            return true;
          }
          setModel(arg);
          setInput("");
          return true;
        }
        onSend(`Current model: ${model}. Use /model <id> to switch.`);
        setInput("");
        return true;
      }
      if (cmd === "/help") {
        onSend("**Local commands:** /clear, /model <id>, /compact, /memory, /help\n**Memex workflows:** /workshop [idea], /grill [idea], /design [prompt], /build [task], /swarm [task], /plan [task], /research [query], /think [question], /cad [prompt]\n**Agent flows:** /flow-blockout [desc], /flow-batch-edit [desc], /flow-audit [desc], /flow-scaffold [desc], /flow-variants [desc], /agent-flows");
        setInput("");
        return true;
      }
      // Pass through to backend: Claude Code + Memex workflow commands + Agent Flows
      if ([
        "/compact", "/plan", "/memory", "/workshop", "/grill", "/design",
        "/build", "/swarm", "/research", "/think", "/cad",
        "/flow-blockout", "/flow-batch-edit", "/flow-audit", "/flow-scaffold", "/flow-variants", "/agent-flows"
      ].includes(cmd)) {
        onSend(raw);
        setInput("");
        return true;
      }
      return false;
    },
    [activeConversationId, deleteConversation, model, onSend, setModel]
  );

  const handleSend = useCallback(() => {
    if (!input.trim() || isStreaming) return;
    if (input.trimStart().startsWith("/") && executeSlash(input.trim())) {
      if (textareaRef.current) textareaRef.current.style.height = "auto";
      return;
    }
    onSend(input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [executeSlash, input, isStreaming, onSend]);

  useEffect(() => {
    vimHandleSendRef.current = handleSend;
  }, [handleSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (isSlash && matches.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSlashIndex((i) => (i + 1) % matches.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSlashIndex((i) => (i - 1 + matches.length) % matches.length);
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
        e.preventDefault();
        const selected = matches[slashIndex];
        if (selected) {
          setInput(selected.cmd + " ");
          if (textareaRef.current) textareaRef.current.focus();
        }
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setInput("");
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  useEffect(() => {
    const onPrefill = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (typeof detail !== "string") return;
      setInput(detail);
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(detail.length, detail.length);
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 200) + "px";
      });
    };
    window.addEventListener("chat:prefill", onPrefill);
    return () => window.removeEventListener("chat:prefill", onPrefill);
  }, []);

  return (
    <div className="border-t border-[var(--chat-border)] bg-[var(--chat-surface)] p-3 md:p-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:pb-[max(1.25rem,env(safe-area-inset-bottom))]">
      <div className="relative flex items-end gap-2 max-w-5xl mx-auto">
        {isSlash && matches.length > 0 && (
          <div
            className="absolute bottom-full mb-2 left-0 right-12 max-h-72 overflow-y-auto rounded-xl border border-[var(--chat-border)] bg-[var(--chat-elevated)] shadow-2xl z-20 py-1 divide-y divide-[var(--chat-border)]/30 backdrop-blur-md"
            style={{ boxShadow: "var(--elev-2)" }}
            role="listbox"
            aria-label="Slash commands"
          >
            {matches.map((c, idx) => (
              <button
                key={c.cmd}
                type="button"
                role="option"
                aria-selected={idx === slashIndex}
                onMouseEnter={() => setSlashIndex(idx)}
                onClick={() => {
                  setInput(c.cmd + " ");
                  if (textareaRef.current) textareaRef.current.focus();
                }}
                className={cn(
                  "w-full text-left px-3.5 py-2 text-xs transition-colors flex items-start gap-2.5 group",
                  idx === slashIndex ? "bg-[var(--hover-tint)] text-[var(--chat-text)]" : "text-[var(--chat-text)]/85 hover:bg-[var(--hover-tint)]"
                )}
                title={c.description}
              >
                <span className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-[var(--chat-accent)]">{c.cmd}</span>
                    <span className="font-medium text-[var(--chat-text)]/90">{c.label}</span>
                    <span className={cn(
                      "text-[10px] px-1.5 py-0.5 rounded font-medium",
                      c.category === "Flow"
                        ? "bg-purple-500/15 text-purple-400 border border-purple-500/30"
                        : c.category === "Workflow"
                        ? "bg-accent/15 text-accent border border-accent/30"
                        : "bg-[var(--chat-surface)] text-[var(--chat-muted)] border border-[var(--chat-border)]"
                    )}>
                      {c.category}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-[var(--chat-muted)] leading-relaxed line-clamp-2">
                    {c.description}
                  </p>
                </span>
                <span className="text-[10px] font-mono text-[var(--chat-muted)]/60 px-1.5 py-0.5 rounded bg-[var(--chat-surface)] mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  Tab ↹
                </span>
              </button>
            ))}
          </div>
        )}
        {vimMode && (
          <div className="absolute bottom-full left-0 mb-1 px-2 py-0.5 text-[10px] font-mono rounded bg-[var(--chat-surface)] border border-[var(--chat-border)] text-[var(--chat-accent)]">
            -- {vim.mode.toUpperCase()} --
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={vimMode ? vim.onKeyDown : handleKeyDown}
          onKeyUp={vimMode ? vim.onKeyUp : undefined}
          placeholder={vimMode && vim.mode === "normal" ? "NORMAL — press i to insert" : (placeholder || "Send a message...")}
          rows={1}
          enterKeyHint="send"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize={vimMode ? "off" : "sentences"}
          spellCheck={false}
          className={cn(
            "input-field flex-1 resize-none scrollbar-thin",
            "px-3.5 py-3 md:px-4 md:py-3.5 text-[15px] leading-[1.55]",
            vimMode && vim.mode === "normal" && "caret-transparent"
          )}
        />
        {isStreaming ? (
          <IconButton
            label="Stop generation"
            icon={<Square size={16} />}
            onClick={onStop}
            variant="danger"
            size="md"
            className="md:w-11 md:h-11"
          />
        ) : (
          <>
            <ChatSettingsMenu />
            <IconButton
              label="Send message"
              icon={<Send size={16} />}
              onClick={handleSend}
              disabled={!input.trim()}
              variant={input.trim() ? "primary" : "secondary"}
              size="md"
              className="md:w-11 md:h-11"
            />
          </>
        )}
      </div>
    </div>
  );
}
