"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState, useRef, useEffect } from "react";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useAccess } from "@/lib/hooks/use-access";
import {
  isNavigationItemActive,
  primaryNavigation,
  secondaryNavigation,
} from "@/lib/config/navigation";
import { cn } from "@/lib/utils/cn";
import {
  Plus,
  MessageSquare,
  LogOut,
  LogIn,
  ChevronDown,
  History,
  Trash2,
} from "lucide-react";
import { useConversationSync } from "@/lib/hooks/use-conversation-sync";

function MemexWordmark() {
  return (
    <div className="flex items-center gap-2 select-none">
      <svg width="20" height="23" viewBox="0 0 28 32" fill="none">
        <path
          d="M14 1L26 8V22L14 29L2 22V8L14 1Z"
          stroke="var(--chat-accent-strong)"
          strokeWidth="1.5"
          fill="color-mix(in srgb, var(--chat-accent) 8%, transparent)"
        />
        <circle cx="14" cy="15" r="2.5" fill="var(--chat-accent-strong)" opacity="0.7" />
      </svg>
      <span className="text-sm font-semibold tracking-wide text-[var(--chat-text)]">
        MEMEX
      </span>
    </div>
  );
}

export function TopBar() {
  const pathname = usePathname();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const { deleteConversation } = useConversationSync();
  const { isAdmin, authenticated, displayName } = useAccess();

  const [historyOpen, setHistoryOpen] = useState(false);
  const historyRef = useRef<HTMLDivElement>(null);

  const visiblePrimary = useMemo(
    () => primaryNavigation.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin],
  );
  const visibleSecondary = useMemo(
    () => secondaryNavigation.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin],
  );
  const allNav = [...visiblePrimary, ...visibleSecondary];

  useEffect(() => {
    if (!historyOpen) return;
    const handler = (e: MouseEvent) => {
      if (historyRef.current && !historyRef.current.contains(e.target as Node))
        setHistoryOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [historyOpen]);

  const isChat = pathname.startsWith("/chat");

  return (
    <header className="topbar flex items-center gap-2 px-3 h-11 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] flex-shrink-0">
      {/* Wordmark */}
      <Link href="/chat" className="mr-2 flex-shrink-0">
        <MemexWordmark />
      </Link>

      <div className="w-px h-5 bg-[var(--divider)] flex-shrink-0" />

      {/* Primary + secondary nav */}
      <nav className="flex items-center gap-0.5 flex-1 overflow-x-auto scrollbar-none">
        {allNav.map((item) => {
          const Icon = item.icon;
          const active = isNavigationItemActive(item, pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors flex-shrink-0",
                active
                  ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
                  : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)]"
              )}
            >
              <Icon size={13} className="flex-shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Right side actions */}
      <div className="flex items-center gap-1 flex-shrink-0 ml-2">
        {/* New chat */}
        <button
          type="button"
          onClick={() => {
            const id = createConversation();
            setActive(id);
          }}
          title="New conversation"
          className="w-7 h-7 flex items-center justify-center rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
        >
          <Plus size={14} />
        </button>

        {/* Chat history popover */}
        <div ref={historyRef} className="relative">
          <button
            type="button"
            onClick={() => setHistoryOpen((o) => !o)}
            title="Chat history"
            className={cn(
              "inline-flex items-center gap-1 px-2 h-7 rounded-md text-xs transition-colors",
              historyOpen
                ? "bg-[var(--chat-accent)] text-white"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)]"
            )}
          >
            <History size={13} />
            <ChevronDown size={10} className={cn("transition-transform", historyOpen && "rotate-180")} />
          </button>

          {historyOpen && (
            <div className="absolute right-0 top-full mt-1 w-72 z-50 rounded-md border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden shadow-lg">
              <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)]">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--chat-muted)]">
                  Recent conversations
                </span>
                <button
                  type="button"
                  onClick={() => {
                    const id = createConversation();
                    setActive(id);
                    setHistoryOpen(false);
                  }}
                  className="inline-flex items-center gap-1 text-[11px] text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)] transition-colors"
                >
                  <Plus size={11} /> New
                </button>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {conversations.length === 0 ? (
                  <div className="px-3 py-4 text-xs text-[var(--chat-muted)] text-center">
                    No conversations yet
                  </div>
                ) : (
                  conversations.slice(0, 30).map((conv) => (
                    <div
                      key={conv.id}
                      className={cn(
                        "group flex items-center gap-2 px-3 py-2 text-xs cursor-pointer transition-colors",
                        conv.id === activeId
                          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_12%,transparent)] text-[var(--chat-accent-strong)]"
                          : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
                      )}
                      onClick={() => {
                        setActive(conv.id);
                        setHistoryOpen(false);
                      }}
                    >
                      <MessageSquare size={12} className="flex-shrink-0" />
                      <span className="flex-1 truncate">{conv.title || "New conversation"}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 text-[var(--chat-subtle)] hover:text-red-400 transition-all"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div className="w-px h-5 bg-[var(--divider)]" />

        {/* User */}
        {authenticated ? (
          <a
            href="/api/auth/logout"
            title={`Sign out (${displayName})`}
            className="inline-flex items-center gap-1.5 px-2 h-7 rounded-md text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
          >
            <span className="hidden sm:inline max-w-[80px] truncate">{displayName}</span>
            <LogOut size={13} />
          </a>
        ) : (
          <a
            href="/api/auth/login"
            className="inline-flex items-center gap-1.5 px-2 h-7 rounded-md text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
          >
            <LogIn size={13} />
          </a>
        )}
      </div>
    </header>
  );
}
