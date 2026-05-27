"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";

export function LCARSDataStream({ lines = 5, className }: { lines?: number; className?: string }) {
  const [data, setData] = useState<string[]>([]);
  const isLcars = typeof document !== "undefined" && document.documentElement.getAttribute("data-theme")?.startsWith("lcars");

  useEffect(() => {
    if (!isLcars) return;
    
    const generateLine = () => {
      const p1 = Math.floor(Math.random() * 90 + 10);
      const p2 = Math.floor(Math.random() * 9000 + 1000);
      return `${p1} ${p2}`;
    };

    const initialData = Array(lines).fill(0).map(generateLine);
    setData(initialData);

    const interval = setInterval(() => {
      setData((prev) => {
        const next = [...prev];
        // Only update a random line to look more realistic than a full redraw
        const i = Math.floor(Math.random() * lines);
        next[i] = generateLine();
        return next;
      });
    }, 400);

    return () => clearInterval(interval);
  }, [lines, isLcars]);

  if (!isLcars) return null;

  return (
    <div className={cn("font-mono text-[9px] leading-[1.2] text-[var(--chat-muted)] opacity-80 tabular-nums flex flex-col items-end", className)}>
      {data.map((line, i) => (
        <div key={i}>{line}</div>
      ))}
    </div>
  );
}
