"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";

const TABS = [
  { label: "Dashboard", href: "/ops" },
  { label: "Traces", href: "/ops/traces" },
] as const;

export default function OpsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-full">
      {/* Tab Bar */}
      <div className="flex border-b border-zinc-800 bg-[#0a0a14] px-4">
        {TABS.map((tab) => {
          const active = tab.href === "/ops"
            ? pathname === "/ops"
            : pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "px-4 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "text-cyan-400 border-b-2 border-cyan-400"
                  : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Page Content */}
      {children}
    </div>
  );
}
