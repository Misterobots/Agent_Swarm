"use client";

import { useRef, useEffect, useState } from "react";

interface ResizableDividerProps {
  direction: "horizontal" | "vertical";
  onResize?: (delta: number) => void;
}

export function ResizableDivider({ direction, onResize }: ResizableDividerProps) {
  const [isDragging, setIsDragging] = useState(false);
  const dividerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (onResize) {
        const delta = direction === "horizontal" ? e.movementX : e.movementY;
        onResize(delta);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, direction, onResize]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  return (
    <div
      ref={dividerRef}
      onMouseDown={handleMouseDown}
      className={`
        bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors cursor-${direction === "horizontal" ? "col" : "row"}-resize
        ${direction === "horizontal" ? "w-1 hover:w-2" : "h-1 hover:h-2"}
        ${isDragging ? "bg-[var(--chat-accent)]" : ""}
      `}
      style={{
        userSelect: "none",
        zIndex: isDragging ? 10 : 1,
      }}
    />
  );
}
