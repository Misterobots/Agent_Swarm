"use client";

import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { NAV_ITEMS } from "./nav-items";
import { NodeStatus } from "@/components/shared/node-status";
import { cn } from "@/lib/utils/cn";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Sidebar() {
  const pathname = usePathname();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const model = useSettingsStore((s) => s.model);

  const isChat = pathname?.startsWith("/chat");

  return (
    <div className="flex flex-col h-full bg-[#0a0a14] border-r border-zinc-800">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-zinc-800">
        <h1 className="text-base font-semibold text-cyan-400 tracking-wide">
          HIVE MIND
        </h1>
        <p className="text-[10px] text-zinc-600 mt-0.5">AI Swarm Interface</p>
      </div>

      {/* Section Nav */}
      <nav className="px-2 py-2 border-b border-zinc-800 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-cyan-600/20 text-cyan-400"
                  : "text-zinc-500 hover:bg-zinc-800/40 hover:text-zinc-300"
              )}
            >
              <Icon size={15} className="flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Chat-specific: New Chat + Conversation List */}
      {isChat && (
        <>
          <div className="px-3 py-2">
            <button
              onClick={() => createConversation(model)}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 rounded-lg border border-zinc-700 border-dashed hover:border-cyan-600 hover:text-cyan-400 transition-colors"
            >
              <Plus size={14} />
              New Chat
            </button>
          </div>

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
        </>
      )}

      {/* Spacer when not on chat */}
      {!isChat && <div className="flex-1" />}

      {/* Node Health (bottom) */}
      <div className="border-t border-zinc-800 px-1 py-2">
        <NodeStatus />
      </div>
    </div>
  );
}
