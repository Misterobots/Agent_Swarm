import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";

interface WorkspaceShellProps {
  title: string;
  description: string;
  icon: LucideIcon;
  /** Optional actions rendered on the right side of the header. */
  actions?: React.ReactNode;
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
  actions,
  children,
}: WorkspaceShellProps) {
  return (
    <div className="flex h-full flex-col bg-[var(--chat-bg)] text-[var(--chat-text)]">
      <div
        className="relative bg-[var(--chat-surface)] py-5"
        style={{ paddingLeft: "calc(var(--sidebar-rail-pad, 0px) + 1.5rem)", paddingRight: "1.5rem" }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="rounded-md p-2.5 text-[var(--chat-accent)] flex-shrink-0"
              style={{
                background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 4%, transparent))",
                border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
                boxShadow: "var(--elev-1), inset 0 1px 0 rgba(255,255,255,0.04)",
              }}
            >
              <Icon size={18} />
            </div>
            <div className="min-w-0">
              <h1 className="text-lg font-semibold tracking-tight text-[var(--chat-text)] truncate">{title}</h1>
              <p className="mt-0.5 text-[13px] text-[var(--chat-muted)]">{description}</p>
            </div>
          </div>
          {actions && <div className="flex-shrink-0">{actions}</div>}
        </div>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-6">{children}</div>
    </div>
  );
}

export function WorkspaceSection({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">{title}</h2>
          {description ? <p className="mt-1 text-[13px] text-[var(--chat-muted)]">{description}</p> : null}
        </div>
        {actions && <div className="flex-shrink-0">{actions}</div>}
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
      className="lift group surface block p-4 transition-colors hover:border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-[var(--chat-text)]">{title}</h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--chat-muted)]">{description}</p>
        </div>
        <ArrowRight
          size={15}
          className="mt-0.5 shrink-0 text-[var(--chat-muted)] transition-all group-hover:text-[var(--chat-accent)] group-hover:translate-x-0.5"
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
    <div className="rounded-md border border-dashed border-[var(--chat-border)] bg-[color:color-mix(in_srgb,var(--chat-panel)_50%,transparent)] p-5">
      <h3 className="text-sm font-medium text-[var(--chat-text)]">{title}</h3>
      <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--chat-muted)]">{body}</p>
    </div>
  );
}
