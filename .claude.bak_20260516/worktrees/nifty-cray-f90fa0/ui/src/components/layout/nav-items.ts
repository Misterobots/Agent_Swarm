import {
  MessageSquare,
  Code2,
  Shield,
  Wrench,
  BarChart3,
  BookOpen,
  FlaskConical,
  Palette,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Art Studio", href: "/art-studio", icon: Palette },
  { label: "Dev", href: "/dev", icon: Code2 },
  { label: "Ops", href: "/ops", icon: Shield },
  { label: "Training", href: "/training", icon: FlaskConical },
  { label: "Tools", href: "/tools", icon: Wrench },
  { label: "Monitor", href: "/monitor", icon: BarChart3 },
  { label: "Docs", href: "/docs", icon: BookOpen },
  { label: "Settings", href: "/settings", icon: Settings },
];
