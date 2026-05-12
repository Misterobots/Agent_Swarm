"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";

const TABS = [
  { label: "Dashboard", href: "/operations" },
  { label: "Traces", href: "/monitoring/traces" },
] as const;

export default function OpsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-full">
      {/* Tab Bar */}
      <div className="flex border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-4">
        {TABS.map((tab) => {
          const active = tab.href === "/operations"
            ? pathname === "/operations"
            : pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "px-4 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
                  : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Page Content */}
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}
