"use client";

/**
 * Wraps an anchor control (e.g. a toolbar chip) and overlays a small "New" dot
 * while the user hasn't dismissed the given feature. The dot is dismissed when
 * the user interacts with the wrapped control — onClickCapture fires before the
 * control's own onClick, so the toggle still happens.
 *
 *   <FeatureCalloutBadge feature="swarm_v1">
 *     <button ...>Swarm</button>
 *   </FeatureCalloutBadge>
 *
 * When the feature isn't "new" (already seen, or store not yet hydrated) the
 * children render untouched with no extra wrapper.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";
import { useFeatureCallout } from "@/lib/hooks/use-feature-callout";
import type { FeatureKey } from "@/lib/onboarding/feature-registry";
import { FeatureCalloutPopover } from "./FeatureCalloutPopover";

export function FeatureCalloutBadge({
  feature,
  children,
  className,
}: {
  feature: FeatureKey;
  children: ReactNode;
  className?: string;
}) {
  const { isNew, isPopoverOpen, meta, dismiss } = useFeatureCallout(feature);

  if (!isNew) return <>{children}</>;

  const onTryIt = meta.tryItPrompt
    ? () => {
        window.dispatchEvent(
          new CustomEvent("chat:prefill", { detail: meta.tryItPrompt })
        );
        dismiss();
      }
    : undefined;

  return (
    <span
      className={cn("relative inline-flex", className)}
      onClickCapture={dismiss}
    >
      {children}
      <span
        aria-label="New"
        className="pointer-events-none absolute -top-1 -right-1 h-2 w-2 rounded-full bg-[var(--chat-accent)] ring-2 ring-[var(--chat-surface)] animate-pulse"
      />
      {isPopoverOpen && (
        <FeatureCalloutPopover meta={meta} onTryIt={onTryIt} onDismiss={dismiss} />
      )}
    </span>
  );
}
