"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface IconButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Required for accessibility — describes the action. */
  label: string;
  icon: React.ReactNode;
  variant?: Variant;
  size?: Size;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary:   "btn-primary",
  secondary: "btn-secondary",
  ghost:     "bg-transparent text-[var(--chat-muted)] border border-transparent hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)]",
  danger:    "bg-red-600 hover:bg-red-500 text-white border border-red-700",
};

const SIZE_CLASS: Record<Size, string> = {
  sm: "w-8  h-8  rounded-md",
  md: "w-10 h-10 rounded-md",
  lg: "w-11 h-11 rounded-md",
};

/**
 * Square icon-only button. Always requires a `label` for screen readers.
 */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "secondary", size = "md", className, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={rest.title ?? label}
      className={cn(
        "inline-flex items-center justify-center transition-all duration-150",
        "focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed",
        SIZE_CLASS[size],
        VARIANT_CLASS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
    </button>
  );
});
