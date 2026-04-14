import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bot,
  FileText,
  GraduationCap,
  Hammer,
  HeartPulse,
  ImagePlus,
  LayoutDashboard,
  MessageSquare,
  Mic2,
  Paintbrush,
  Radar,
  Scale,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
  matchPrefixes?: string[];
  children?: NavigationItem[];
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
    icon: Radar,
    matchPrefixes: ["/monitoring"],
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
        label: "Control Room",
        href: "/monitoring/control-room",
        icon: ShieldCheck,
        matchPrefixes: ["/monitoring/control-room"],
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
    label: "Media",
    href: "/media",
    icon: Paintbrush,
    matchPrefixes: ["/media"],
    children: [
      {
        label: "Images",
        href: "/media/images",
        icon: ImagePlus,
        matchPrefixes: ["/media/images"],
      },
      {
        label: "Voice",
        href: "/media/voice",
        icon: Mic2,
        matchPrefixes: ["/media/voice"],
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
    ],
  },
  {
    label: "Training",
    href: "/training",
    icon: GraduationCap,
    matchPrefixes: ["/training"],
  },
];

export const secondaryNavigation: NavigationItem[] = [
  {
    label: "Operations",
    href: "/operations",
    icon: LayoutDashboard,
    matchPrefixes: ["/operations"],
  },
  {
    label: "Governance",
    href: "/governance",
    icon: Scale,
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