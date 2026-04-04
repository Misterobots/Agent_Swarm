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
    <div className="flex flex-col h-full bg-[var(--chat-sidebar)] border-r border-[var(--chat-border)]">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[var(--chat-border)]">
        <h1 className="text-base font-semibold text-[var(--chat-accent-strong)] tracking-wide">
          HIVE MIND
        </h1>
        <p className="text-[10px] text-[var(--chat-muted)] mt-0.5">AI Swarm Interface</p>
      </div>

      {/* Section Nav */}
      <nav className="px-2 py-2 border-b border-[var(--chat-border)] space-y-0.5">
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
                  ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_16%,transparent)] text-[var(--chat-accent-strong)]"
                  : "text-[var(--chat-muted)] hover:bg-[var(--chat-soft)] hover:text-[var(--chat-text)]"
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
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--chat-text)] rounded-lg border border-[var(--chat-border)] border-dashed hover:border-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)] transition-colors"
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
                    ? "bg-[var(--chat-soft)] text-[var(--chat-text)]"
                    : "text-[var(--chat-muted)] hover:bg-[var(--chat-soft)] hover:text-[var(--chat-text)]"
                )}
              >
                <MessageSquare size={14} className="flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="block truncate">{conv.title}</span>
                  {(conv.resumeCheckpoints?.length || conv.lastTurnId) && (
                    <span className="block text-[10px] text-[var(--chat-muted)] truncate">
                      {conv.resumeCheckpoints?.length ? `${conv.resumeCheckpoints.length} checkpoints` : "Continuable"}
                    </span>
                  )}
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-[var(--chat-muted)] hover:text-red-400 transition-all"
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
      <div className="border-t border-[var(--chat-border)] px-1 py-2">
        <NodeStatus />
      </div>
    </div>
  );
}
