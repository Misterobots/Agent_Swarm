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
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-[var(--chat-border)] bg-[var(--chat-surface)] pb-[env(safe-area-inset-bottom)]">
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
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 w-full h-full transition-colors touch-target",
                active
                  ? "text-[var(--chat-accent)]"
                  : "text-[var(--chat-muted)]"
              )}
            >
              <item.icon size={20} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
        <button
          onClick={onMenuPress}
          className={cn(
            "flex flex-col items-center justify-center gap-0.5 w-full h-full transition-colors touch-target",
            !anyTabActive
              ? "text-[var(--chat-accent)]"
              : "text-[var(--chat-muted)] active:text-[var(--chat-accent)]"
          )}
        >
          <Menu size={20} />
          <span className="text-[10px] font-medium">More</span>
        </button>
      </div>
    </nav>
  );
}
