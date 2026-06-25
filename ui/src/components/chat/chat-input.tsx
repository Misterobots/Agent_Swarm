"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Square } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useAccess } from "@/lib/hooks/use-access";
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
  const { isAdmin } = useAccess();
  const vimMode = useSettingsStore((s) => s.vimMode);
  // vim hook initialized with a stable ref; actual handleSend assigned after its definition
  const vimHandleSendRef = useRef<() => void>(() => {});
  const vim = useVimInput(textareaRef as React.RefObject<HTMLTextAreaElement>, () => vimHandleSendRef.current());

  // Claude Code commands (local handling) + Memex workflow commands (passed to backend)
  const commands = [
    // Local: chat & model management
    "/clear", "/model", "/compact", "/memory", "/help",
    // Backend: Memex workflows
    "/workshop", "/grill", "/design", "/build", "/swarm", "/plan", "/research", "/think",
  ];
  const isSlash = input.trimStart().startsWith("/");
  const commandQuery = input.trimStart().slice(1).toLowerCase();
  const matches = commands.filter((c) => c.slice(1).startsWith(commandQuery));

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
          if (!canSelectModel(arg, isAdmin)) {
            onSend("Access denied: selected model is admin-only.");
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
        onSend("**Local commands:** /clear, /model <id>, /compact, /memory, /help\n**Memex workflows:** /workshop [idea], /grill [idea], /design [prompt], /build [task], /swarm [task], /plan [task], /research [query], /think [question]");
        setInput("");
        return true;
      }
      // Pass through to backend: Claude Code + Memex workflow commands
      if (["/compact", "/plan", "/memory", "/workshop", "/grill", "/design", "/build", "/swarm", "/research", "/think"].includes(cmd)) {
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
  }, [input, isStreaming, onSend]);

  // Keep the vim hook's submit ref in sync with the real handleSend
  vimHandleSendRef.current = handleSend;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  // Listen for prefill events (e.g. from EmptyChatState starter chips)
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
            className="absolute bottom-full mb-2 left-0 right-12 rounded-md border border-[var(--chat-border)] bg-[var(--chat-elevated)] overflow-hidden z-20"
            style={{ boxShadow: "var(--elev-2)" }}
          >
            {matches.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setInput(c + " ")}
                className="w-full text-left px-3 py-2 text-xs text-[var(--chat-text)] hover:bg-[var(--hover-tint)]"
              >
                {c}
              </button>
            ))}
          </div>
        )}
        {/* Vim mode indicator */}
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
