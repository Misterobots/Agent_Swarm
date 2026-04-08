import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";

interface WorkspaceShellProps {
  title: string;
  description: string;
  icon: LucideIcon;
  children?: React.ReactNode;
}

interface WorkspaceLinkCardProps {
  title: string;
  description: string;
  href: string;
}

export function WorkspaceShell({
  title,
  description,
  icon: Icon,
  children,
}: WorkspaceShellProps) {
  return (
    <div className="flex h-full flex-col bg-[#0b0f15] text-zinc-100">
      <div className="border-b border-zinc-800 bg-[#0e1117] px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-cyan-900/60 bg-cyan-950/40 p-2 text-cyan-300">
            <Icon size={18} />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-zinc-100">{title}</h1>
            <p className="mt-1 text-sm text-zinc-400">{description}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">{children}</div>
    </div>
  );
}

export function WorkspaceSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <div className="mb-3">
        <h2 className="text-sm font-medium text-zinc-200">{title}</h2>
        {description ? <p className="mt-1 text-xs text-zinc-500">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function WorkspaceCardGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

export function WorkspaceLinkCard({ title, description, href }: WorkspaceLinkCardProps) {
  return (
    <Link
      href={href}
      className="group rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 transition-colors hover:border-cyan-700/60 hover:bg-zinc-900"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-zinc-100">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-zinc-400">{description}</p>
        </div>
        <ArrowRight
          size={16}
          className="mt-0.5 shrink-0 text-zinc-600 transition-colors group-hover:text-cyan-400"
        />
      </div>
    </Link>
  );
}

export function WorkspacePlaceholder({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/40 p-5">
      <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{body}</p>
    </div>
  );
}