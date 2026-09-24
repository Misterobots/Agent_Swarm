import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  BookOpen,
  FileText,
  HeartPulse,
  LayoutDashboard,
  Network,
  Radar,
  Settings,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
  matchPrefixes?: string[];
  children?: NavigationItem[];
  adminOnly?: boolean;
}

// Product surfaces (chat, research, routines, design/art-studio, code, palace)
// moved to the Desktop app — see plans/peppy-orbiting-honey.md. The remaining
// primary nav is the standalone Memory/Codebase Graph viewer, kept as-is
// pending its own split decision; everything else here is now admin-only.
export const primaryNavigation: NavigationItem[] = [
  {
    label: "Graph",
    href: "/graph",
    icon: Network,
    matchPrefixes: ["/graph"],
    adminOnly: true,
  },
];

export const secondaryNavigation: NavigationItem[] = [
  {
    label: "Control Center",
    href: "/mission-control",
    icon: LayoutDashboard,
    matchPrefixes: [
      "/mission-control",
      "/operations",
      "/ops",
      "/control",
      "/monitoring/control-room",
      "/governance",
    ],
    adminOnly: true,
  },
  {
    label: "Monitoring",
    href: "/monitoring",
    icon: Radar,
    matchPrefixes: ["/monitoring"],
    adminOnly: true,
    children: [
      {
        label: "Dashboard",
        href: "/monitoring/dashboard",
        icon: Activity,
        matchPrefixes: ["/monitoring/dashboard"],
      },
      {
        label: "Grafana",
        href: "/monitoring/grafana",
        icon: BarChart3,
        matchPrefixes: ["/monitoring/grafana"],
      },
      {
        label: "Swarm Observer",
        href: "/monitoring/swarm-observer",
        icon: Radar,
        matchPrefixes: ["/monitoring/swarm-observer"],
      },
      {
        label: "Traces",
        href: "/monitoring/traces",
        icon: Activity,
        matchPrefixes: ["/monitoring/traces"],
      },
      {
        label: "Evidence Locker",
        href: "/monitoring/evidence-locker",
        icon: FileText,
        matchPrefixes: ["/monitoring/evidence-locker"],
      },
      {
        label: "Service Health",
        href: "/monitoring/service-health",
        icon: HeartPulse,
        matchPrefixes: ["/monitoring/service-health"],
      },
    ],
  },
];

export const utilityNavigation: NavigationItem[] = [
  {
    label: "Documentation",
    href: "/docs",
    icon: BookOpen,
    matchPrefixes: ["/docs"],
  },
  {
    label: "Settings",
    href: "/settings",
    icon: Settings,
    matchPrefixes: ["/settings"],
  },
];

// Chat/dev/research/routines all moved to the Desktop app (see
// plans/peppy-orbiting-honey.md) — the website has no conversation route left,
// so this always reports false. Kept (rather than removed) so the sidebar/
// mobile-drawer/top-bar chrome that gates on it doesn't need a parallel rewrite.
export function isConversationRoute(_pathname: string | null | undefined): boolean {
  return false;
}

export function conversationExperienceForPath(
  _pathname: string | null | undefined,
): "chat" | "code" | "research" | "routines" {
  return "chat";
}

export function isNavigationItemActive(item: NavigationItem, pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  const prefixes = item.matchPrefixes ?? [item.href];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
