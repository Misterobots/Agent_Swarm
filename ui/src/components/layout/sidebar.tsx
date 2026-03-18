"use client";

import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { ModeSwitcher } from "./mode-switcher";
import { cn } from "@/lib/utils/cn";
import { Plus, Trash2, MessageSquare } from "lucide-react";

export function Sidebar() {
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const model = useSettingsStore((s) => s.model);

  return (
    <div className="flex flex-col h-full bg-[#0a0a14] border-r border-zinc-800">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-zinc-800">
        <h1 className="text-base font-semibold text-cyan-400 tracking-wide">
          HIVE MIND
        </h1>
        <p className="text-[10px] text-zinc-600 mt-0.5">AI Swarm Interface</p>
      </div>

      {/* Mode Switcher */}
      <div className="px-3 py-3 border-b border-zinc-800">
        <ModeSwitcher />
      </div>

      {/* New Chat */}
      <div className="px-3 py-2">
        <button
          onClick={() => createConversation(model)}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 rounded-lg border border-zinc-700 border-dashed hover:border-cyan-600 hover:text-cyan-400 transition-colors"
        >
          <Plus size={14} />
          New Chat
        </button>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 scrollbar-thin scrollbar-thumb-zinc-800">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => setActive(conv.id)}
            className={cn(
              "group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm mb-0.5 transition-colors",
              conv.id === activeId
                ? "bg-zinc-800/70 text-zinc-200"
                : "text-zinc-500 hover:bg-zinc-800/40 hover:text-zinc-300"
            )}
          >
            <MessageSquare size={14} className="flex-shrink-0" />
            <span className="flex-1 truncate">{conv.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteConversation(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-red-400 transition-all"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
