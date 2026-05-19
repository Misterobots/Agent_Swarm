"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";

const PalaceViewer = dynamic(
  () => import("@/components/palace/palace-viewer").then((m) => m.PalaceViewer),
  { ssr: false },
);

export default function PalacePage() {
  return (
    <div className="h-full w-full relative" style={{ background: "var(--chat-bg)" }}>
      <Suspense
        fallback={
          <div className="flex items-center justify-center h-full w-full">
            <div className="flex flex-col items-center gap-3">
              <div
                className="w-10 h-10 border-2 rounded-full animate-spin"
                style={{
                  borderColor: "var(--chat-border)",
                  borderTopColor: "var(--chat-accent)",
                }}
              />
              <span style={{ color: "var(--chat-muted)" }} className="text-sm">
                Entering the Palace…
              </span>
            </div>
          </div>
        }
      >
        <PalaceViewer />
      </Suspense>
    </div>
  );
}
