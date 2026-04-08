import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bot,
  Gavel,
  Image,
  MessageSquare,
  Settings,
  Shield,
  SlidersHorizontal,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
  matchPrefixes?: string[];
}

export const primaryNavigation: NavigationItem[] = [
  {
    label: "Chat",
    href: "/chat",
    icon: MessageSquare,
    matchPrefixes: ["/chat"],
  },
  {
    label: "Developer",
    href: "/dev",
    icon: Bot,
    matchPrefixes: ["/dev"],
  },
  {
    label: "Monitoring",
    href: "/monitoring",
    icon: Activity,
    matchPrefixes: ["/monitoring"],
  },
  {
    label: "Media",
    href: "/media",
    icon: Image,
    matchPrefixes: ["/media"],
  },
  {
    label: "Training",
    href: "/training",
    icon: SlidersHorizontal,
    matchPrefixes: ["/training"],
  },
];

export const secondaryNavigation: NavigationItem[] = [
  {
    label: "Control",
    href: "/control",
    icon: Shield,
    matchPrefixes: ["/control"],
  },
  {
    label: "Governance",
    href: "/governance",
    icon: Gavel,
    matchPrefixes: ["/governance"],
  },
];

export const utilityNavigation: NavigationItem[] = [
  {
    label: "Settings",
    href: "/settings",
    icon: Settings,
    matchPrefixes: ["/settings"],
  },
];

export function isConversationRoute(pathname: string): boolean {
  return pathname === "/chat" || pathname.startsWith("/dev");
}

export function isNavigationItemActive(item: NavigationItem, pathname: string): boolean {
  const prefixes = item.matchPrefixes ?? [item.href];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}