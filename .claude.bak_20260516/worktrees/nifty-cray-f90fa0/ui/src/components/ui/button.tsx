"use client";

import { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
  fullWidth?: boolean;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary:   "btn-primary",
  secondary: "btn-secondary",
  ghost:     "bg-transparent text-[var(--chat-text)] border border-transparent hover:bg-[var(--hover-tint)] hover:border-[var(--chat-border)]",
  danger:    "bg-red-600 hover:bg-red-500 text-white border border-red-700",
};

const SIZE_CLASS: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-md",
  md: "h-10 px-4 text-sm gap-2 rounded-md",
  lg: "h-11 px-5 text-[15px] gap-2 rounded-md",
};

/**
 * Polished button with consistent height, focus ring, and hover-lift.
 * Composes the .btn-primary / .btn-secondary CSS classes from globals.css.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    iconLeft,
    iconRight,
    fullWidth = false,
    children,
    className,
    disabled,
    type = "button",
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center font-medium tracking-tight whitespace-nowrap transition-all duration-150",
        "focus-visible:outline-none disabled:cursor-not-allowed",
        SIZE_CLASS[size],
        VARIANT_CLASS[variant],
        fullWidth && "w-full",
        loading && "opacity-90",
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 size={size === "sm" ? 13 : 15} className="animate-spin" />
      ) : (
        iconLeft
      )}
      {children && <span className="min-w-0 truncate">{children}</span>}
      {!loading && iconRight}
    </button>
  );
});
