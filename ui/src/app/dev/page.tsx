"use client";

import { DevWorkspace } from "@/components/dev/dev-workspace";
import { useAccess } from "@/lib/hooks/use-access";
import { useDevSessionSync } from "@/lib/hooks/use-dev-session-sync";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function DevPage() {
  const { isAdmin, loading } = useAccess();
  const router = useRouter();

  // Cross-device dev session sync — must be called unconditionally (React rules)
  useDevSessionSync();

  useEffect(() => {
    if (!loading && !isAdmin) {
      router.replace("/chat");
    }
  }, [loading, isAdmin, router]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-[var(--chat-muted)] text-sm">
        Checking access…
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <DevWorkspace />
    </div>
  );
}
