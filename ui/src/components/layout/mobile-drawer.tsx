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
} from "@/lib/config/navigation";

// Items shown in the More drawer (Media + Palace only)
const MOBILE_MORE_HREFS = new Set(["/media", "/palace"]);
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

  const visibleExplore = useMemo(
    () => primaryNavigation.filter((item) => MOBILE_MORE_HREFS.has(item.href)),
    []
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
          "sidebar-wrapper fixed top-0 left-0 bottom-0 z-50 w-72 flex flex-col transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "-translate-x-full pointer-events-none"
        )}
        style={{ boxShadow: open ? "var(--elev-3)" : "none" }}
      >
        {/* Header */}
        <div className="relative flex items-center justify-between px-4 py-5">
          <div>
            <h1 className="text-[15px] font-semibold text-[var(--chat-text)] tracking-tight leading-none">
              Memex
            </h1>
            <p className="text-[10px] text-[var(--chat-subtle)] mt-1.5 tracking-wide uppercase">AI Swarm Interface</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 inline-flex items-center justify-center rounded-md text-[var(--chat-subtle)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] transition-colors"
            aria-label="Close menu"
          >
            <X size={16} />
          </button>
          <div className="absolute bottom-0 left-3 right-3 divider" />
        </div>

        {/* Mode Switcher — admin only, matches desktop sidebar behaviour */}
        {isAdmin && (
          <div className="relative px-3 py-3">
            <ModeSwitcher />
            <div className="absolute bottom-0 left-3 right-3 divider" />
          </div>
        )}

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin">
          <DrawerSection title="Explore">
            {visibleExplore.map((item) => (
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
                  className="btn-secondary w-full flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-md"
                >
                  <Plus size={14} />
                  <span>New Chat</span>
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
                        "group flex items-center gap-2 mx-2 px-3 py-2 rounded-md cursor-pointer text-[13px] transition-colors",
                        conv.id === activeId
                          ? "sidebar-active"
                          : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
                      )}
                    >
                      <MessageSquare
                        size={13}
                        className={cn(
                          "flex-shrink-0",
                          conv.id === activeId ? "text-[var(--chat-accent)]" : ""
                        )}
                      />
                      <span className="flex-1 truncate">{conv.title}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                        className="text-[var(--chat-subtle)] hover:text-red-400 transition-colors"
                        aria-label="Delete conversation"
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
        <div className="relative px-4 py-3">
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
              className="btn-secondary inline-flex items-center justify-center gap-2 text-[13px] px-3 py-1.5 rounded-md w-full"
              title="Sign in with Authentik"
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
      <div className="px-4 pb-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--chat-subtle)]">
          {title}
        </span>
      </div>
      <div className="space-y-px">{children}</div>
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
            "relative flex items-center gap-2.5 mx-2 px-3 py-2 rounded-md text-[13px] transition-colors duration-150 w-[calc(100%-1rem)]",
            active
              ? "sidebar-active"
              : "text-[var(--chat-muted)] active:bg-[var(--hover-tint)]"
          )}
        >
          <Icon size={15} className={cn("shrink-0 transition-colors", active && "text-[var(--chat-accent)]")} />
          <span className="truncate flex-1 text-left">{item.label}</span>
          <ChevronDown
            size={13}
            className={cn(
              "shrink-0 transition-transform duration-200 text-[var(--chat-subtle)]",
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
          <div className="ml-5 mt-0.5 space-y-px border-l border-[var(--chat-border)] pl-2">
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
        "relative flex items-center gap-2.5 mx-2 px-3 py-2 rounded-md text-[13px] transition-colors duration-150",
        active
          ? "sidebar-active"
          : "text-[var(--chat-muted)] active:bg-[var(--hover-tint)]"
      )}
    >
      <Icon size={15} className={cn("shrink-0 transition-colors", active && "text-[var(--chat-accent)]")} />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}
