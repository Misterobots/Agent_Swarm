"use client";

import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  icon: LucideIcon;
  title: string;
  children?: React.ReactNode;
}

export function PageHeader({ icon: Icon, title, children }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-zinc-800 bg-[#0e1117] px-4 py-3">
      <div className="flex items-center gap-2">
        <Icon size={18} className="text-zinc-400" />
        <h1 className="text-sm font-medium text-zinc-300">{title}</h1>
      </div>
      {children}
    </div>
  );
}
