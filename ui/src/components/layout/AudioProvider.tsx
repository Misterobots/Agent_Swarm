"use client";

import { useEffect, useRef } from "react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { playHover, playClick, playKeystroke } from "@/lib/audio/ui-sfx";

/**
 * Global UI sound provider.
 *
 * Listens to mouseover / mousedown / keydown at the document level (capture
 * phase) and triggers the matching synthesized sound. The active theme is
 * read from the settings store and passed to each play* call so the
 * per-theme profile in `theme-sfx-profiles.ts` is applied.
 *
 * The active theme is held in a ref so theme changes don't tear down the
 * event listeners on every switch.
 */
export function AudioProvider() {
  const soundEnabled = useSettingsStore(s => s.soundEnabled);
  const theme = useSettingsStore(s => s.theme);

  // Hold the current theme in a ref so listeners always see the latest value
  // without re-attaching on every theme switch.
  const themeRef = useRef(theme);
  useEffect(() => {
    themeRef.current = theme;
  }, [theme]);

  useEffect(() => {
    if (!soundEnabled) return;

    // Handle mouseover for hover sounds
    const onMouseOver = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;

      // Check if target or parent is interactive
      const isInteractive = target.closest('button, a, [role="button"], [role="menuitem"]');
      if (isInteractive) {
        // Prevent spamming if already hovering inside the same button
        if (!e.relatedTarget || !isInteractive.contains(e.relatedTarget as Node)) {
          playHover(themeRef.current);
        }
      }
    };

    // Handle mousedown for click sounds
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;

      const isInteractive = target.closest('button, a, [role="button"], [role="menuitem"]');
      if (isInteractive) {
        playClick(themeRef.current);
      }
    };

    // Handle keydown for typing sounds
    const onKeyDown = (e: KeyboardEvent) => {
      // Ignore modifier keys
      if (['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) return;

      const target = e.target as HTMLElement;
      if (!target) return;

      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;
      if (isInput) {
        playKeystroke(themeRef.current);
      }
    };

    // Use capturing phase so we get the events even if propagation is stopped by a component
    document.addEventListener("mouseover", onMouseOver, true);
    document.addEventListener("mousedown", onMouseDown, true);
    document.addEventListener("keydown", onKeyDown, true);

    return () => {
      document.removeEventListener("mouseover", onMouseOver, true);
      document.removeEventListener("mousedown", onMouseDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
    };
  }, [soundEnabled]);

  return null; // Silent global provider
}
