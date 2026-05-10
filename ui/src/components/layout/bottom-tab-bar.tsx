"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, Palette, Wrench, Settings, Menu } from "lucide-react";
import { isNavigationItemActive } from "@/lib/config/navigation";
import { cn } from "@/lib/utils/cn";
import type { LucideIcon } from "lucide-react";

interface TabItem {
  label: string;
  href: string;
  icon: LucideIcon;
  matchPrefixes?: string[];
}

const TAB_ITEMS: TabItem[] = [
  { label: "Chat", href: "/chat", icon: MessageSquare, matchPrefixes: ["/chat"] },
  { label: "Art", href: "/art-studio", icon: Palette, matchPrefixes: ["/art-studio", "/media"] },
  { label: "Tools", href: "/tools", icon: Wrench, matchPrefixes: ["/tools", "/monitoring", "/training", "/operations", "/governance", "/docs"] },
  { label: "Settings", href: "/settings", icon: Settings, matchPrefixes: ["/settings"] },
];

interface BottomTabBarProps {
  onMenuPress: () => void;
}

export function BottomTabBar({ onMenuPress }: BottomTabBarProps) {
  const pathname = usePathname();

  // "More" highlights when current route isn't covered by any tab
  const anyTabActive = TAB_ITEMS.some((item) =>
    isNavigationItemActive({ ...item, matchPrefixes: item.matchPrefixes }, pathname)
  );

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 bg-[var(--chat-surface)] pb-[env(safe-area-inset-bottom)]"
      style={{
        borderTop: "1px solid var(--chat-border)",
        boxShadow: "var(--elev-2)",
      }}
    >
      <div className="flex items-center justify-around h-14">
        {TAB_ITEMS.map((item) => {
          const active = isNavigationItemActive(
            { ...item, matchPrefixes: item.matchPrefixes },
            pathname
          );
          return (
            <Link
              key={item.href}
              href={item.href}
              className="flex flex-col items-center justify-center w-full h-full touch-target relative"
            >
              {active && (
                <span
                  className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-8 rounded-b-full bg-[var(--chat-accent)]"
                  style={{ boxShadow: "0 0 8px rgba(var(--chat-accent-rgb), 0.6)" }}
                />
              )}
              <item.icon
                size={20}
                className={cn(
                  "transition-all",
                  active ? "text-[var(--chat-accent)] scale-110" : "text-[var(--chat-muted)]"
                )}
              />
              <span
                className={cn(
                  "text-[10px] font-medium mt-0.5 transition-colors",
                  active ? "text-[var(--chat-accent)]" : "text-[var(--chat-muted)]"
                )}
              >
                {item.label}
              </span>
            </Link>
          );
        })}
        <button
          onClick={onMenuPress}
          className="flex flex-col items-center justify-center w-full h-full touch-target relative"
        >
          {!anyTabActive && (
            <span
              className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-8 rounded-b-full bg-[var(--chat-accent)]"
              style={{ boxShadow: "0 0 8px rgba(var(--chat-accent-rgb), 0.6)" }}
            />
          )}
          <Menu
            size={20}
            className={cn(
              "transition-all",
              !anyTabActive ? "text-[var(--chat-accent)] scale-110" : "text-[var(--chat-muted)]"
            )}
          />
          <span
            className={cn(
              "text-[10px] font-medium mt-0.5 transition-colors",
              !anyTabActive ? "text-[var(--chat-accent)]" : "text-[var(--chat-muted)]"
            )}
          >
            More
          </span>
        </button>
      </div>
    </nav>
  );
}
