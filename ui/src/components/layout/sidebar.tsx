"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import {
  isConversationRoute,
  isNavigationItemActive,
  primaryNavigation,
  secondaryNavigation,
  utilityNavigation,
} from "@/lib/config/navigation";
import { ModeSwitcher } from "./mode-switcher";
import { cn } from "@/lib/utils/cn";
import { Plus, Trash2, MessageSquare, Search, X } from "lucide-react";
import { BuddyWidget } from "@/components/buddy/buddy-widget";

function HiveLogo() {
  return (
    <svg width="28" height="32" viewBox="0 0 28 32" fill="none" className="sidebar-logo">
      {/* Outer hexagon */}
      <path
        d="M14 1L26 8V22L14 29L2 22V8L14 1Z"
        stroke="var(--chat-accent-strong)"
        strokeWidth="1.5"
        fill="color-mix(in srgb, var(--chat-accent) 8%, transparent)"
      />
      {/* Inner hexagon */}
      <path
        d="M14 7L21 11V19L14 23L7 19V11L14 7Z"
        stroke="var(--chat-accent)"
        strokeWidth="0.8"
        opacity="0.5"
        fill="none"
      />
      {/* Center node */}
      <circle cx="14" cy="15" r="2.5" fill="var(--chat-accent-strong)" opacity="0.7" />
      {/* Network lines from center to vertices */}
      <line x1="14" y1="15" x2="14" y2="7" stroke="var(--chat-accent)" strokeWidth="0.5" opacity="0.3" />
      <line x1="14" y1="15" x2="21" y2="11" stroke="var(--chat-accent)" strokeWidth="0.5" opacity="0.3" />
      <line x1="14" y1="15" x2="21" y2="19" stroke="var(--chat-accent)" strokeWidth="0.5" opacity="0.3" />
      <line x1="14" y1="15" x2="14" y2="23" stroke="var(--chat-accent)" strokeWidth="0.5" opacity="0.3" />
      <line x1="14" y1="15" x2="7" y2="19" stroke="var(--chat-accent)" strokeWidth="0.5" opacity="0.3" />
      <line x1="14" y1="15" x2="7" y2="11" stroke="var(--chat-accent)" strokeWidth="0.5" opacity="0.3" />
      {/* Vertex dots */}
      <circle cx="14" cy="7" r="1" fill="var(--chat-accent)" opacity="0.5" />
      <circle cx="21" cy="11" r="1" fill="var(--chat-accent)" opacity="0.5" />
      <circle cx="21" cy="19" r="1" fill="var(--chat-accent)" opacity="0.5" />
      <circle cx="14" cy="23" r="1" fill="var(--chat-accent)" opacity="0.5" />
      <circle cx="7" cy="19" r="1" fill="var(--chat-accent)" opacity="0.5" />
      <circle cx="7" cy="11" r="1" fill="var(--chat-accent)" opacity="0.5" />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const model = useSettingsStore((s) => s.model);
  const showConversations = isConversationRoute(pathname);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter(
      (conv) =>
        conv.title.toLowerCase().includes(q) ||
        conv.messages.some((m) => m.content.toLowerCase().includes(q))
    );
  }, [conversations, searchQuery]);

  return (
    <div className="sidebar-wrapper relative flex flex-col h-full bg-[color:color-mix(in_srgb,var(--chat-bg)_85%,black)] border-r border-[var(--chat-border)]">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-3">
          <HiveLogo />
          <div>
            <h1 className="text-base font-semibold text-[var(--chat-accent-strong)] tracking-wide">
              HIVE MIND
            </h1>
            <p className="text-[10px] text-[var(--chat-muted)] mt-0.5">AI Swarm Interface</p>
          </div>
        </div>
      </div>

      {/* Mode Switcher */}
      <div className="px-3 py-3 border-b border-[var(--chat-border)]">
        <ModeSwitcher />
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin">
        <SidebarSection title="Workspaces">
          {primaryNavigation.map((item) => (
            <div key={item.href}>
              <SidebarNavItem
                href={item.href}
                label={item.label}
                active={isNavigationItemActive(item, pathname)}
                icon={item.icon}
              />
              {item.children && isNavigationItemActive(item, pathname) && (
                <div className="mt-1 space-y-0.5 pb-1">
                  {item.children.map((child) => (
                    <SidebarNavItem
                      key={child.href}
                      href={child.href}
                      label={child.label}
                      active={isNavigationItemActive(child, pathname)}
                      icon={child.icon}
                      compact
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </SidebarSection>

        <SidebarSection title="Operations">
          {secondaryNavigation.map((item) => (
            <SidebarNavItem key={item.href} href={item.href} label={item.label} active={isNavigationItemActive(item, pathname)} icon={item.icon} />
          ))}
        </SidebarSection>

        <SidebarSection title="Preferences">
          {utilityNavigation.map((item) => (
            <SidebarNavItem key={item.href} href={item.href} label={item.label} active={isNavigationItemActive(item, pathname)} icon={item.icon} />
          ))}
        </SidebarSection>

        {showConversations ? (
          <>
            <div className="px-3 py-2">
              <button
                onClick={() => createConversation(model)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--chat-text)] rounded-lg border border-[var(--chat-border)] border-dashed hover:border-[var(--chat-accent)] hover:text-[var(--chat-accent)] transition-colors"
              >
                <Plus size={14} />
                New Chat
              </button>
            </div>

            {/* Quick Search */}
            {conversations.length > 1 && (
              <div className="px-3 pb-2">
                <div className="relative">
                  <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--chat-muted)]" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search chats..."
                    className="w-full pl-7 pr-7 py-1.5 text-xs rounded-md bg-[var(--chat-panel)] border border-[var(--chat-border)] text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:border-[var(--chat-accent)] focus:outline-none"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>
            )}

            <SidebarSection title={searchQuery ? `Results (${filteredConversations.length})` : "Chat History"}>
              {filteredConversations.length === 0 ? (
                <p className="px-3 py-2 text-xs text-[var(--chat-muted)]">
                  {searchQuery ? "No matching conversations." : "Start a conversation to pin chat history here."}
                </p>
              ) : (
                filteredConversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => setActive(conv.id)}
                    className={cn(
                      "group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm mb-0.5 transition-colors",
                      conv.id === activeId
                        ? "bg-[var(--chat-panel)] text-[var(--chat-text)]"
                        : "text-[var(--chat-muted)] hover:bg-[color:color-mix(in_srgb,var(--chat-panel)_50%,transparent)] hover:text-[var(--chat-text)]"
                    )}
                  >
                    <MessageSquare size={14} className="flex-shrink-0" />
                    <span className="flex-1 truncate">{conv.title}</span>
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
                ))
              )}
            </SidebarSection>
          </>
        ) : null}
      </div>

      {/* Buddy companion */}
      <BuddyWidget />

      {/* Status footer */}
      <div className="px-4 py-3 border-t border-[var(--chat-border)]">
        <div className="flex items-center gap-2 text-[10px] text-[var(--chat-muted)]">
          <span className="sidebar-status-dot w-1.5 h-1.5 rounded-full bg-[var(--chat-accent)]" />
          <span>Swarm Online</span>
        </div>
      </div>
    </div>
  );
}

function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-2 px-3 pb-1.5">
        <span className="sidebar-section-title text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--chat-muted)]">
          {title}
        </span>
        <span className="flex-1 h-px bg-[var(--chat-border)] opacity-50" />
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function SidebarNavItem({
  href,
  label,
  active,
  icon: Icon,
  compact = false,
}: {
  href: string;
  label: string;
  active: boolean;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  compact?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "relative flex items-center rounded-lg transition-all duration-150",
        compact ? "mx-4 gap-2 px-3 py-1.5 text-xs" : "mx-2 gap-2.5 px-3 py-2 text-sm",
        active
          ? "sidebar-active bg-[var(--chat-panel)] text-[var(--chat-text)]"
          : "text-[var(--chat-muted)] hover:bg-[color:color-mix(in_srgb,var(--chat-panel)_50%,transparent)] hover:text-[var(--chat-text)]"
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-[var(--chat-accent)]" />
      )}
      <Icon size={compact ? 13 : 16} className={cn("shrink-0 transition-colors", active && "text-[var(--chat-accent)]")} />
      <span className="truncate">{label}</span>
    </Link>
  );
}
