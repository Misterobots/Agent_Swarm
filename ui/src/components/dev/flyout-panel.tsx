"use client";

import { ReactNode, useEffect, useRef } from "react";
import { X } from "lucide-react";

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

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Flyout Panel */}
      <div
        ref={panelRef}
        className={`fixed top-0 right-0 h-full bg-[var(--chat-bg)] border-l border-[var(--chat-border)] shadow-2xl z-50 flex flex-col transition-transform duration-200 ${
          isOpen ? 'translate-x-0' : 'translate-x-full pointer-events-none'
        }`}
        style={{ width }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--chat-border)] bg-gradient-to-r from-[var(--chat-surface)] to-transparent">
          <div className="flex items-center gap-2">
            {icon && <div className="text-[var(--chat-accent)]">{icon}</div>}
            <h2 className="text-sm font-semibold text-[var(--chat-text)]">{title}</h2>
          </div>
          <div className="flex items-center gap-2">
            {headerAction}
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
              title="Close (Esc)"
            >
              <X size={16} className="text-[var(--chat-muted)]" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </div>
    </>
  );
}
