"use client";

import { useEffect, useState } from "react";
import { isDesktop, desktop, type MemexDesktopBridge } from "@/lib/desktop";

/**
 * Returns whether the UI is running inside the Memex Desktop app,
 * and the bridge object if so.
 *
 * Usage:
 *   const { inDesktop, bridge } = useDesktop();
 *   if (inDesktop) bridge.fs.readFile("/some/path");
 */
export function useDesktop(): { inDesktop: boolean; bridge: MemexDesktopBridge | null } {
  const [inDesktop, setInDesktop] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setInDesktop(isDesktop()), 0);
    return () => clearTimeout(timer);
  }, []);

  return { inDesktop, bridge: inDesktop ? desktop() : null };
}
