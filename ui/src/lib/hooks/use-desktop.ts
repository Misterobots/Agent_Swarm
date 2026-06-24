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
    setInDesktop(isDesktop());
  }, []);

  return { inDesktop, bridge: inDesktop ? desktop() : null };
}
