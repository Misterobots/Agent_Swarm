"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils/cn";

type Padding = "none" | "sm" | "md" | "lg";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padding?: Padding;
  /** Use the elevated tier (popovers, active rows). */
  elevated?: boolean;
  /** Add hover-lift transition (only when used as a button/link). */
  interactive?: boolean;
  as?: "div" | "section" | "article";
}

const PADDING_CLASS: Record<Padding, string> = {
  none: "",
  sm:   "p-3",
  md:   "p-4 md:p-5",
  lg:   "p-5 md:p-6",
};

/**
 * Surface container with consistent border, radius, elevation, and inset
 * highlight. Use `elevated` for popovers / active rows that need an extra tier.
 */
export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  {
    padding = "md",
    elevated = false,
    interactive = false,
    as = "section",
    className,
    children,
    ...rest
  },
  ref,
) {
  const Tag = as as React.ElementType;
  return (
    <Tag
      ref={ref}
      className={cn(
        elevated ? "surface-elevated" : "surface",
        PADDING_CLASS[padding],
        interactive && "lift cursor-pointer",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
});

export function CardHeader({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("mb-3 md:mb-4", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...rest }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn(
        "text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]",
        className,
      )}
      {...rest}
    >
      {children}
    </h2>
  );
}
