"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Square } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useAccess } from "@/lib/hooks/use-access";
import { canSelectModel } from "@/lib/utils/model-access";
import { ChatSettingsMenu } from "./chat-settings-menu";

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

  const commands = ["/clear", "/model", "/compact", "/plan", "/memory", "/help"];
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
        onSend("Available slash commands: /clear, /model <id>, /compact, /plan, /memory, /help");
        setInput("");
        return true;
      }
      if (cmd === "/compact" || cmd === "/plan" || cmd === "/memory") {
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
    <div className="border-t border-[var(--chat-border)] bg-[var(--chat-surface)] p-3 md:p-5">
      <div className="relative flex items-end gap-2 max-w-3xl mx-auto">
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
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Send a message..."}
          rows={1}
          className={cn(
            "input-field flex-1 resize-none scrollbar-thin",
            "px-3.5 py-3 md:px-4 md:py-3.5 text-[15px] leading-[1.55]"
          )}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="lift flex-shrink-0 w-10 h-10 md:w-11 md:h-11 rounded-md bg-red-600 hover:bg-red-500 text-white flex items-center justify-center"
            style={{ boxShadow: "var(--elev-1), inset 0 1px 0 rgba(255,255,255,0.15)" }}
            aria-label="Stop"
          >
            <Square size={16} />
          </button>
        ) : (
          <>
            <ChatSettingsMenu />
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              aria-label="Send message"
              className={cn(
                "flex-shrink-0 w-10 h-10 md:w-11 md:h-11 rounded-md flex items-center justify-center",
                input.trim()
                  ? "btn-primary"
                  : "bg-[var(--chat-soft)] text-[var(--chat-subtle)] border border-[var(--chat-border)] cursor-not-allowed"
              )}
            >
              <Send size={16} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
