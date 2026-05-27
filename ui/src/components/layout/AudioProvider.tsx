"use client";

import { useEffect } from "react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { playHover, playClick, playKeystroke } from "@/lib/audio/ui-sfx";

export function AudioProvider() {
  const soundEnabled = useSettingsStore(s => s.soundEnabled);

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
          playHover();
        }
      }
    };

    // Handle mousedown for click sounds
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;
      
      const isInteractive = target.closest('button, a, [role="button"], [role="menuitem"]');
      if (isInteractive) {
        playClick();
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
        playKeystroke();
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
