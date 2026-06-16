import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  BookOpen,
  Castle,
  Code2,
  FileText,
  GraduationCap,
  Hammer,
  HeartPulse,
  ImagePlus,
  LayoutDashboard,
  MessageSquare,
  Mic2,
  Network,
  Paintbrush,
  Radar,
  Settings,
  Sparkles,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
  matchPrefixes?: string[];
  children?: NavigationItem[];
  adminOnly?: boolean;
}

export const primaryNavigation: NavigationItem[] = [
  {
    label: "Chat",
    href: "/chat",
    icon: MessageSquare,
    matchPrefixes: ["/chat"],
  },
  {
    label: "Media",
    href: "/media",
    icon: Paintbrush,
    matchPrefixes: ["/media", "/art-studio"],
    children: [
      {
        label: "Studio",
        href: "/art-studio",
        icon: ImagePlus,
        matchPrefixes: ["/art-studio", "/media/images"],
      },
      {
        label: "Action Figure",
        href: "/media/action-figure",
        icon: Sparkles,
        matchPrefixes: ["/media/action-figure"],
      },
      {
        label: "Creature Forge",
        href: "/media/creature-forge",
        icon: Hammer,
        matchPrefixes: ["/media/creature-forge"],
      },
      {
        label: "Voice",
        href: "/media/voice",
        icon: Mic2,
        matchPrefixes: ["/media/voice"],
      },
    ],
  },
  {
    label: "Palace",
    href: "/palace",
    icon: Castle,
    matchPrefixes: ["/palace", "/graph"],
    children: [
      {
        label: "Memory Graph",
        href: "/graph",
        icon: Network,
        matchPrefixes: ["/graph"],
      },
    ],
  },
  {
    label: "Dev",
    href: "/dev",
    icon: Code2,
    matchPrefixes: ["/dev"],
    adminOnly: true,
  },
];

export const secondaryNavigation: NavigationItem[] = [
  {
    label: "Mission Control",
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
  {
    label: "Training",
    href: "/training",
    icon: GraduationCap,
    matchPrefixes: ["/training"],
    adminOnly: true,
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

export function isConversationRoute(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return pathname === "/chat" || pathname.startsWith("/dev");
}

export function isNavigationItemActive(item: NavigationItem, pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  const prefixes = item.matchPrefixes ?? [item.href];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}