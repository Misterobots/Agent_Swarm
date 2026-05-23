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
import { Plus, Trash2, MessageSquare, Search, X, LogOut, LogIn, User, PanelLeftClose } from "lucide-react";
import { BuddyWidget } from "@/components/buddy/buddy-widget";
import { useAccess } from "@/lib/hooks/use-access";
import { useConversationSync } from "@/lib/hooks/use-conversation-sync";

function MemexLogo() {
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

export function Sidebar({ onCollapse, slim = false, onExpand }: { onCollapse?: () => void; slim?: boolean; onExpand?: () => void } = {}) {
  const pathname = usePathname();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const { deleteConversation } = useConversationSync();
  const model = useSettingsStore((s) => s.model);
  const { isAdmin, authenticated, displayName } = useAccess();
  const showConversations = isConversationRoute(pathname);
  const [searchQuery, setSearchQuery] = useState("");

  const visiblePrimary = useMemo(() =>
    primaryNavigation.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin]
  );
  const visibleSecondary = useMemo(() =>
    secondaryNavigation.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin]
  );

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter(
      (conv) =>
        conv.title.toLowerCase().includes(q) ||
        conv.messages.some((m) => m.content.toLowerCase().includes(q))
    );
  }, [conversations, searchQuery]);

  const groupedConversations = useMemo(
    () => groupByDate(filteredConversations),
    [filteredConversations],
  );

  // ── Slim (icon-only rail) mode ────────────────────────────────────────────
  if (slim) {
    const allNav = [...visiblePrimary, ...visibleSecondary, ...utilityNavigation];
    return (
      <div className="sidebar-wrapper relative flex flex-col h-full items-center py-2 gap-1">
        {/* Logo — click to expand */}
        <button
          onClick={onExpand}
          className="w-9 h-9 flex items-center justify-center rounded-md text-[var(--chat-accent)] hover:bg-[var(--hover-tint)] transition-colors mb-1"
          title="Expand sidebar"
          aria-label="Expand sidebar"
        >
          <MemexLogo />
        </button>
        <div className="w-8 h-px bg-[var(--divider)] mb-1" />
        {/* Icon-only nav */}
        <div className="flex-1 flex flex-col gap-0.5 w-full px-1 overflow-y-auto scrollbar-none">
          {allNav.map((item) => {
            const Icon = item.icon;
            const active = isNavigationItemActive(item, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.label}
                aria-label={item.label}
                className={cn(
                  "flex items-center justify-center w-full h-9 rounded-md transition-colors",
                  active
                    ? "sidebar-active text-[var(--chat-accent)]"
                    : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
                )}
              >
                <Icon size={16} className="shrink-0" />
              </Link>
            );
          })}
        </div>
        {/* Footer — swarm dot only */}
        <div className="flex flex-col items-center gap-2 pb-1">
          <div className="w-8 h-px bg-[var(--divider)]" />
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 sidebar-status-dot" title="Swarm Online" />
        </div>
      </div>
    );
  }

  return (
    <div className="sidebar-wrapper relative flex flex-col h-full">
      {/* Logo */}
      <div className="px-4 py-5 relative">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <MemexLogo />
            <div className="min-w-0">
              <h1 className="text-[15px] font-semibold text-[var(--chat-text)] tracking-tight leading-none">
                Memex
              </h1>
              <p className="text-[10px] text-[var(--chat-subtle)] mt-1.5 tracking-wide uppercase">AI Swarm Interface</p>
            </div>
          </div>
          {onCollapse && (
            <button
              onClick={onCollapse}
              className="flex-shrink-0 w-7 h-7 inline-flex items-center justify-center rounded-md text-[var(--chat-subtle)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
              title="Slim sidebar"
              aria-label="Slim sidebar"
            >
              <PanelLeftClose size={15} />
            </button>
          )}
        </div>
        <div className="absolute bottom-0 left-3 right-3 divider" />
      </div>

      {/* Mode Switcher - Admin only */}
      {isAdmin && (
        <div className="px-3 py-3 relative">
          <ModeSwitcher />
          <div className="absolute bottom-0 left-3 right-3 divider" />
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin">
        <SidebarSection title="Workspaces">
          {visiblePrimary.map((item) => (
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

        {visibleSecondary.length > 0 && (
          <SidebarSection title="Operations">
            {visibleSecondary.map((item) => (
              <SidebarNavItem key={item.href} href={item.href} label={item.label} active={isNavigationItemActive(item, pathname)} icon={item.icon} />
            ))}
          </SidebarSection>
        )}

        <SidebarSection title="Preferences">
          {utilityNavigation.map((item) => (
            <SidebarNavItem key={item.href} href={item.href} label={item.label} active={isNavigationItemActive(item, pathname)} icon={item.icon} />
          ))}
        </SidebarSection>

        {showConversations ? (
          <>
            <div className="sidebar-new-chat px-3 pt-3 pb-2 space-y-2">
              <button
                onClick={() => createConversation(model)}
                className="btn-secondary w-full flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-md transition-all"
              >
                <Plus size={14} />
                <span>New Chat</span>
              </button>

              {conversations.length > 1 && (
                <div className="relative">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--chat-subtle)] pointer-events-none" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search chats…"
                    className="input-field w-full !py-1.5 pl-8 pr-7 text-[13px]"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--chat-subtle)] hover:text-[var(--chat-text)] transition-colors"
                      aria-label="Clear search"
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
              )}
            </div>

            {filteredConversations.length === 0 ? (
              <div className="mx-3 mt-2 rounded-md border border-dashed border-[var(--chat-border)] px-3 py-4 text-center">
                <p className="text-[12px] text-[var(--chat-muted)]">
                  {searchQuery ? "No matches" : "Your conversations will appear here"}
                </p>
              </div>
            ) : (
              <div className="mt-1">
                {groupedConversations.map((group) => (
                  <div key={group.label} className="mb-3">
                    <div className="px-4 pb-1.5 pt-2">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--chat-subtle)]">
                        {searchQuery && group.label === groupedConversations[0].label
                          ? `Results (${filteredConversations.length})`
                          : group.label}
                      </span>
                    </div>
                    <div className="space-y-px">
                      {group.items.map((conv) => (
                        <ConversationRow
                          key={conv.id}
                          title={conv.title}
                          isActive={conv.id === activeId}
                          onClick={() => setActive(conv.id)}
                          onDelete={() => deleteConversation(conv.id)}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : null}
      </div>

      {/* Buddy companion */}
      <BuddyWidget />

      {/* User & status footer */}
      <div className="px-4 py-3 relative space-y-2">
        <div className="absolute top-0 left-3 right-3 divider" />
        {authenticated ? (
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div
                className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 text-[var(--chat-accent)]"
                style={{
                  background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 4%, transparent))",
                  border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
                  boxShadow: "var(--inset-highlight)",
                }}
              >
                <User size={13} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-medium text-[var(--chat-text)] truncate leading-none">{displayName}</p>
                {isAdmin && (
                  <span className="mt-1 inline-block text-[9px] font-semibold px-1.5 py-0.5 rounded-sm bg-[var(--chat-accent-soft)] text-[var(--chat-accent-strong)] uppercase tracking-wider">
                    Admin
                  </span>
                )}
              </div>
            </div>
            <a
              href="https://auth.shivelymedia.com/if/flow/default-invalidation-flow/"
              className="flex-shrink-0 w-7 h-7 inline-flex items-center justify-center rounded-md text-[var(--chat-subtle)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut size={13} />
            </a>
          </div>
        ) : (
          <a
            href="/api/auth/login"
            className="btn-secondary inline-flex items-center gap-2 text-[13px] px-3 py-1.5 rounded-md w-full justify-center"
            title="Sign in with Authentik"
          >
            <LogIn size={14} />
            <span>Sign in</span>
          </a>
        )}
        <div className="flex items-center gap-1.5 text-[10px] text-[var(--chat-muted)]">
          <span className="sidebar-status-dot w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
          <span>Swarm Online</span>
        </div>
      </div>
    </div>
  );
}


function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="px-4 pb-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--chat-subtle)]">
          {title}
        </span>
      </div>
      <div className="space-y-px">{children}</div>
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
        "relative flex items-center rounded-md transition-colors duration-150",
        compact ? "mx-4 gap-2 px-3 py-1.5 text-xs" : "mx-2 gap-2.5 px-3 py-2 text-sm",
        active
          ? "sidebar-active"
          : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
      )}
    >
      <Icon size={compact ? 13 : 16} className={cn("shrink-0 transition-colors", active && "text-[var(--chat-accent)]")} />
      <span className="truncate">{label}</span>
    </Link>
  );
}

function ConversationRow({
  title,
  isActive,
  onClick,
  onDelete,
}: {
  title: string;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        "group relative flex items-center gap-2 mx-2 px-3 py-2 rounded-md cursor-pointer text-[13px] transition-colors",
        isActive
          ? "sidebar-active"
          : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
      )}
    >
      <MessageSquare
        size={13}
        className={cn(
          "flex-shrink-0 transition-colors",
          isActive ? "text-[var(--chat-accent)]" : ""
        )}
      />
      <span className="flex-1 truncate">{title}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="opacity-0 group-hover:opacity-100 text-[var(--chat-subtle)] hover:text-red-400 transition-all"
        aria-label="Delete conversation"
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
}

interface ConversationGroup {
  label: string;
  items: Array<{ id: string; title: string; updatedAt: number }>;
}

/** Bucket conversations by relative date for sidebar headers. */
function groupByDate(
  conversations: Array<{ id: string; title: string; updatedAt: number }>,
): ConversationGroup[] {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86_400_000;
  const sevenDaysAgo = startOfToday - 6 * 86_400_000;
  const thirtyDaysAgo = startOfToday - 29 * 86_400_000;

  const buckets: Record<string, ConversationGroup["items"]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 Days": [],
    "Previous 30 Days": [],
    Older: [],
  };

  // Conversations come in already sorted (most recent first), preserve that.
  for (const conv of conversations) {
    const t = conv.updatedAt;
    if (t >= startOfToday) buckets.Today.push(conv);
    else if (t >= startOfYesterday) buckets.Yesterday.push(conv);
    else if (t >= sevenDaysAgo) buckets["Previous 7 Days"].push(conv);
    else if (t >= thirtyDaysAgo) buckets["Previous 30 Days"].push(conv);
    else buckets.Older.push(conv);
  }

  return ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older"]
    .map((label) => ({ label, items: buckets[label] }))
    .filter((group) => group.items.length > 0);
}
