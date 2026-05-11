"use client";

import Link from "next/link";
import { ArrowRight, Radar, GraduationCap, LayoutDashboard, Scale, BookOpen } from "lucide-react";
import { useAccess } from "@/lib/hooks/use-access";
import type { LucideIcon } from "lucide-react";

interface HubItem {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
  adminOnly?: boolean;
}

const HUB_ITEMS: HubItem[] = [
  { label: "Monitor",       href: "/monitoring/dashboard", icon: Radar,           description: "Health & swarm telemetry",        adminOnly: true },
  { label: "Training",      href: "/training",             icon: GraduationCap,   description: "Model training & deployment",     adminOnly: true },
  { label: "Operations",    href: "/operations",           icon: LayoutDashboard, description: "Infrastructure & tasks",          adminOnly: true },
  { label: "Governance",    href: "/governance",           icon: Scale,           description: "Policies & compliance",           adminOnly: true },
  { label: "Documentation", href: "/docs",                 icon: BookOpen,        description: "Guides & reference" },
];

export function ToolsHub() {
  const { isAdmin } = useAccess();
  const visible = HUB_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="relative bg-[var(--chat-surface)] px-4 py-4">
        <h1 className="text-[15px] font-semibold tracking-tight text-[var(--chat-text)] leading-none">Tools</h1>
        <p className="text-[11px] text-[var(--chat-subtle)] mt-1.5 uppercase tracking-wide">Lab management &amp; resources</p>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid grid-cols-2 gap-3">
          {visible.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="lift group surface block p-4 transition-colors hover:border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
            >
              <div className="flex items-start justify-between mb-3">
                <div
                  className="w-9 h-9 rounded-md flex items-center justify-center text-[var(--chat-accent)] flex-shrink-0"
                  style={{
                    background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 4%, transparent))",
                    border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
                  }}
                >
                  <item.icon size={17} />
                </div>
                <ArrowRight
                  size={14}
                  className="text-[var(--chat-muted)] transition-all group-hover:text-[var(--chat-accent)] group-hover:translate-x-0.5"
                />
              </div>
              <p className="text-[13px] font-semibold text-[var(--chat-text)]">{item.label}</p>
              <p className="text-[11px] text-[var(--chat-muted)] mt-0.5 leading-relaxed">{item.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
