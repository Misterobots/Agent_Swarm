"use client";

import { useEffect, useCallback, useState } from "react";
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
import { Plus, Trash2, MessageSquare, X, LogOut, LogIn, User, ChevronDown } from "lucide-react";
import { useAccess } from "@/lib/hooks/use-access";
import type { NavigationItem } from "@/lib/config/navigation";
import { useMemo } from "react";

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const pathname = usePathname();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const model = useSettingsStore((s) => s.model);
  const { isAdmin, authenticated, displayName } = useAccess();
  const showConversations = isConversationRoute(pathname);

  const visiblePrimary = useMemo(
    () => primaryNavigation.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin]
  );
  const visibleSecondary = useMemo(
    () => secondaryNavigation.filter((item) => !item.adminOnly || isAdmin),
    [isAdmin]
  );

  // Close drawer on route change
  useEffect(() => {
    onClose();
  }, [pathname, onClose]);

  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const handleBackdropClick = useCallback(() => {
    onClose();
  }, [onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-50 bg-black/50 transition-opacity duration-200",
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
        onClick={handleBackdropClick}
      />

      {/* Drawer panel */}
      <div
        className={cn(
          "fixed top-0 left-0 bottom-0 z-50 w-72 bg-[var(--chat-bg)] border-r border-[var(--chat-border)] flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--chat-border)]">
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-base font-semibold text-[var(--chat-accent-strong)] tracking-wide">
                HIVE MIND
              </h1>
              <p className="text-[10px] text-[var(--chat-muted)] mt-0.5">AI Swarm Interface</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Mode Switcher */}
        <div className="px-3 py-3 border-b border-[var(--chat-border)]">
          <ModeSwitcher />
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin">
          <DrawerSection title="Workspaces">
            {visiblePrimary.map((item) => (
              <DrawerNavItem
                key={item.href}
                item={item}
                pathname={pathname}
                onNavigate={onClose}
              />
            ))}
          </DrawerSection>

          {visibleSecondary.length > 0 && (
            <DrawerSection title="Operations">
              {visibleSecondary.map((item) => (
                <DrawerNavItem
                  key={item.href}
                  item={item}
                  pathname={pathname}
                  onNavigate={onClose}
                />
              ))}
            </DrawerSection>
          )}

          <DrawerSection title="Preferences">
            {utilityNavigation.map((item) => (
              <DrawerNavItem
                key={item.href}
                item={item}
                pathname={pathname}
                onNavigate={onClose}
              />
            ))}
          </DrawerSection>

          {/* Chat History */}
          {showConversations && (
            <>
              <div className="px-3 py-2">
                <button
                  onClick={() => {
                    createConversation(model);
                    onClose();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--chat-text)] rounded-lg border border-[var(--chat-border)] border-dashed hover:border-[var(--chat-accent)] hover:text-[var(--chat-accent)] transition-colors"
                >
                  <Plus size={14} />
                  New Chat
                </button>
              </div>

              <DrawerSection title="Chat History">
                {conversations.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-[var(--chat-muted)]">
                    Start a conversation to see history here.
                  </p>
                ) : (
                  conversations.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => {
                        setActive(conv.id);
                        onClose();
                      }}
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
              </DrawerSection>
            </>
          )}
        </div>

        {/* User footer */}
        <div className="px-4 py-3 border-t border-[var(--chat-border)] space-y-2">
          {authenticated ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <User size={14} className="flex-shrink-0 text-[var(--chat-accent)]" />
                <span className="text-xs text-[var(--chat-text)] truncate">{displayName}</span>
                {isAdmin && (
                  <span className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] text-[var(--chat-accent)]">
                    Admin
                  </span>
                )}
              </div>
              <a
                href="https://auth.shivelymedia.com/flows/-/default/invalidation/"
                className="flex items-center gap-1 text-[10px] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
                title="Sign out"
              >
                <LogOut size={12} />
              </a>
            </div>
          ) : (
            <a
              href="https://auth.shivelymedia.com/"
              className="flex items-center gap-2 text-xs text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)] transition-colors"
            >
              <LogIn size={14} />
              <span>Sign in</span>
            </a>
          )}
        </div>
      </div>
    </>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 px-3 pb-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--chat-muted)]">
          {title}
        </span>
        <span className="flex-1 h-px bg-[var(--chat-border)] opacity-50" />
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function DrawerNavItem({
  item,
  pathname,
  onNavigate,
}: {
  item: NavigationItem;
  pathname: string;
  onNavigate: () => void;
}) {
  const active = isNavigationItemActive(item, pathname);
  const Icon = item.icon;
  const hasChildren = item.children && item.children.length > 0;
  const [expanded, setExpanded] = useState(() => active);

  // Auto-expand when navigating to a child route
  useEffect(() => {
    if (active && hasChildren) setExpanded(true);
  }, [active, hasChildren]);

  if (hasChildren) {
    return (
      <div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className={cn(
            "relative flex items-center gap-2.5 mx-2 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 w-[calc(100%-1rem)]",
            active
              ? "bg-[var(--chat-panel)] text-[var(--chat-text)]"
              : "text-[var(--chat-muted)] active:bg-[color:color-mix(in_srgb,var(--chat-panel)_50%,transparent)]"
          )}
        >
          {active && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-[var(--chat-accent)]" />
          )}
          <Icon size={16} className={cn("shrink-0 transition-colors", active && "text-[var(--chat-accent)]")} />
          <span className="truncate flex-1 text-left">{item.label}</span>
          <ChevronDown
            size={14}
            className={cn(
              "shrink-0 transition-transform duration-200 text-[var(--chat-muted)]",
              expanded && "rotate-180"
            )}
          />
        </button>
        <div
          className={cn(
            "overflow-hidden transition-all duration-200",
            expanded ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
          )}
        >
          <div className="ml-4 mt-0.5 space-y-0.5 border-l border-[var(--chat-border)] pl-2">
            {item.children!.map((child) => (
              <DrawerNavItem
                key={child.href}
                item={child}
                pathname={pathname}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        "relative flex items-center gap-2.5 mx-2 px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
        active
          ? "bg-[var(--chat-panel)] text-[var(--chat-text)]"
          : "text-[var(--chat-muted)] active:bg-[color:color-mix(in_srgb,var(--chat-panel)_50%,transparent)]"
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-[var(--chat-accent)]" />
      )}
      <Icon size={16} className={cn("shrink-0 transition-colors", active && "text-[var(--chat-accent)]")} />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}
