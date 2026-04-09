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
    <div className="flex h-full flex-col bg-[var(--chat-bg)] text-[var(--chat-text)]">
      <div className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-[color:color-mix(in_srgb,var(--chat-accent)_30%,transparent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_10%,transparent)] p-2 text-[var(--chat-accent)]">
            <Icon size={18} />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-[var(--chat-text)]">{title}</h1>
            <p className="mt-1 text-sm text-[var(--chat-muted)]">{description}</p>
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
        <h2 className="text-sm font-medium text-[var(--chat-text)]">{title}</h2>
        {description ? <p className="mt-1 text-xs text-[var(--chat-muted)]">{description}</p> : null}
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
      className="group rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4 transition-colors hover:border-[var(--chat-accent)] hover:bg-[var(--chat-surface)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-[var(--chat-text)]">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--chat-muted)]">{description}</p>
        </div>
        <ArrowRight
          size={16}
          className="mt-0.5 shrink-0 text-[var(--chat-muted)] transition-colors group-hover:text-[var(--chat-accent)]"
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
    <div className="rounded-2xl border border-dashed border-[var(--chat-border)] bg-[var(--chat-panel)] p-5">
      <h3 className="text-sm font-medium text-[var(--chat-text)]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[var(--chat-muted)]">{body}</p>
    </div>
  );
}