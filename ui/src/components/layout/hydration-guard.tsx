"use client";

import { useEffect, useState } from "react";

export function HydrationGuard({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  if (!hydrated) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0e1117]">
        <div className="text-cyan-400 text-sm animate-pulse">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
