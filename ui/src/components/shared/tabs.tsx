"use client";

import { cn } from "@/lib/utils/cn";

interface Tab {
  id: string;
  label: string;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onSelect: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onSelect, className }: TabsProps) {
  return (
    <div className={cn("flex border-b border-zinc-800", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onSelect(tab.id)}
          className={cn(
            "px-4 py-2.5 text-sm font-medium transition-colors",
            active === tab.id
              ? "text-cyan-400 border-b-2 border-cyan-400"
              : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
