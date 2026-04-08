"use client";

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
import { Plus, Trash2, MessageSquare } from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const model = useSettingsStore((s) => s.model);
  const showConversations = isConversationRoute(pathname);

  return (
    <div className="flex flex-col h-full bg-[color:color-mix(in_srgb,var(--chat-bg)_85%,black)] border-r border-[var(--chat-border)]">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[var(--chat-border)]">
        <h1 className="text-base font-semibold text-[var(--chat-accent-strong)] tracking-wide">
          HIVE MIND
        </h1>
        <p className="text-[10px] text-[var(--chat-muted)] mt-0.5">AI Swarm Interface</p>
      </div>

      {/* Mode Switcher */}
      <div className="px-3 py-3 border-b border-[var(--chat-border)]">
        <ModeSwitcher />
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin">
        <SidebarSection title="Workspaces">
          {primaryNavigation.map((item) => (
            <SidebarNavItem key={item.href} href={item.href} label={item.label} active={isNavigationItemActive(item, pathname)} icon={item.icon} />
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

            <SidebarSection title="Chat History">
              {conversations.length === 0 ? (
                <p className="px-3 py-2 text-xs text-[var(--chat-muted)]">
                  Start a conversation to pin chat history here.
                </p>
              ) : (
                conversations.map((conv) => (
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
    </div>
  );
}

function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--chat-muted)]">
        {title}
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
}: {
  href: string;
  label: string;
  active: boolean;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "mx-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
        active
          ? "bg-[var(--chat-panel)] text-[var(--chat-text)]"
          : "text-[var(--chat-muted)] hover:bg-[color:color-mix(in_srgb,var(--chat-panel)_50%,transparent)] hover:text-[var(--chat-text)]"
      )}
    >
      <Icon size={14} className="shrink-0" />
      <span className="truncate">{label}</span>
    </Link>
  );
}
