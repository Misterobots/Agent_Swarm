import { cn } from "@/lib/utils/cn";

interface StatusDotProps {
  status: "ok" | "warn" | "error";
  className?: string;
}

export function StatusDot({ status, className }: StatusDotProps) {
  return (
    <span
      className={cn(
        "inline-block w-2 h-2 rounded-full",
        status === "ok" && "bg-emerald-400",
        status === "warn" && "bg-amber-400",
        status === "error" && "bg-red-400",
        className
      )}
    />
  );
}
