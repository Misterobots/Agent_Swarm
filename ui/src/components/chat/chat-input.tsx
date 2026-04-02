"use client";

import { useState, useRef, useCallback } from "react";
import { Send, Square } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useAccess } from "@/lib/hooks/use-access";
import { canSelectModel } from "@/lib/utils/model-access";

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

  return (
    <div className="border-t border-[#2e2a27] bg-[#10100f] p-4">
      <div className="relative flex items-end gap-2 max-w-3xl mx-auto">
        {isSlash && matches.length > 0 && (
          <div className="absolute bottom-full mb-2 left-0 right-12 rounded-md border border-[#3b332e] bg-[#11100f] overflow-hidden z-20">
            {matches.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setInput(c + " ")}
                className="w-full text-left px-3 py-2 text-xs text-zinc-200 hover:bg-[#1a1917]"
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
            "flex-1 resize-none bg-[#0f0f0f] text-zinc-200 rounded-md px-4 py-3 font-mono",
            "border border-[#3b332e] focus:border-[#cc785c] focus:outline-none",
            "placeholder:text-zinc-500 text-sm leading-relaxed",
            "scrollbar-thin scrollbar-thumb-zinc-700"
          )}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="flex-shrink-0 w-10 h-10 rounded-md bg-red-700 hover:bg-red-600 text-white flex items-center justify-center transition-colors"
          >
            <Square size={16} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className={cn(
              "flex-shrink-0 w-10 h-10 rounded-md flex items-center justify-center transition-colors",
              input.trim()
                ? "bg-[#cc785c] hover:bg-[#d08a71] text-white"
                : "bg-zinc-800 text-zinc-600 cursor-not-allowed"
            )}
          >
            <Send size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
