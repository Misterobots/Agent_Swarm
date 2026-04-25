"use client";

import Link from "next/link";
import { Radar, GraduationCap, LayoutDashboard, Scale, BookOpen } from "lucide-react";
import { useAccess } from "@/lib/hooks/use-access";
import { cn } from "@/lib/utils/cn";
import type { LucideIcon } from "lucide-react";

interface HubItem {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
  adminOnly?: boolean;
}

const HUB_ITEMS: HubItem[] = [
  {
    label: "Monitor",
    href: "/monitoring/dashboard",
    icon: Radar,
    description: "Health & swarm telemetry",
    adminOnly: true,
  },
  {
    label: "Training",
    href: "/training",
    icon: GraduationCap,
    description: "Model training & deployment",
    adminOnly: true,
  },
  {
    label: "Operations",
    href: "/operations",
    icon: LayoutDashboard,
    description: "Infrastructure & tasks",
    adminOnly: true,
  },
  {
    label: "Governance",
    href: "/governance",
    icon: Scale,
    description: "Policies & compliance",
    adminOnly: true,
  },
  {
    label: "Documentation",
    href: "/docs",
    icon: BookOpen,
    description: "Guides & reference",
  },
];

export function ToolsHub() {
  const { isAdmin } = useAccess();
  const visible = HUB_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="px-4 py-4 border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
        <h1 className="text-sm font-semibold text-[var(--chat-text)]">Tools</h1>
        <p className="text-[11px] text-[var(--chat-muted)] mt-0.5">Lab management &amp; resources</p>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid grid-cols-2 gap-3">
          {visible.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col gap-3 p-4 rounded-xl",
                "border border-[var(--chat-border)] bg-[var(--chat-panel)]",
                "active:bg-[var(--chat-soft)] transition-colors"
              )}
            >
              <item.icon size={22} className="text-[var(--chat-accent)]" />
              <div>
                <p className="text-[13px] font-semibold text-[var(--chat-text)]">{item.label}</p>
                <p className="text-[11px] text-[var(--chat-muted)] mt-0.5 leading-snug">{item.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
