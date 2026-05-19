"use client";

import { ReactNode, useEffect, useRef } from "react";
import { X } from "lucide-react";
import { IconButton } from "@/components/ui";

interface FlyoutPanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  width?: string;
  headerAction?: ReactNode;
}

export function FlyoutPanel({
  isOpen,
  onClose,
  title,
  icon,
  children,
  width = "450px",
  headerAction,
}: FlyoutPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity animate-in fade-in"
          onClick={onClose}
        />
      )}

      {/* Flyout Panel */}
      <div
        ref={panelRef}
        className={`fixed top-0 right-0 h-full z-50 flex flex-col transition-transform duration-200 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full pointer-events-none"
        }`}
        style={{
          width,
          background: "var(--chat-bg)",
          borderLeft: "1px solid var(--chat-border)",
          boxShadow: "var(--elev-3)",
        }}
      >
        {/* Header */}
        <div className="relative flex items-center justify-between px-4 py-3 bg-[var(--chat-surface)]">
          <div className="flex items-center gap-2.5 min-w-0">
            {icon && (
              <div
                className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--chat-accent)] flex-shrink-0"
                style={{
                  background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 4%, transparent))",
                  border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
                  boxShadow: "var(--inset-highlight)",
                }}
              >
                {icon}
              </div>
            )}
            <h2 className="text-[13px] font-semibold text-[var(--chat-text)] tracking-tight truncate">{title}</h2>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {headerAction}
            <IconButton
              label="Close"
              icon={<X size={14} />}
              onClick={onClose}
              variant="ghost"
              size="sm"
              title="Close (Esc)"
            />
          </div>
          <div className="absolute bottom-0 left-0 right-0 divider" />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </>
  );
}
