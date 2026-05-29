"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Characters revealed per animation frame (~60 fps → ~180 chars/sec).
 *
 * Deliberately slower than a raw token stream so the typewriter effect is
 * clearly visible during screen recordings.  At 3 chars/frame:
 *   - 300-char response → ~1.7 s of visible animation
 *   - 600-char response → ~3.3 s of visible animation
 *   - 1000-char response → ~5.6 s of visible animation
 */
const CHARS_PER_FRAME = 3;

/**
 * Smoothly reveals text at a natural streaming cadence regardless of whether
 * the backend sends content in tiny trickles or large batches.
 *
 * KEY IMPLEMENTATION NOTES:
 * - We track display position via a ref (displayLenRef) so the RAF loop never
 *   reads stale closures or triggers setState updater side-effects.
 * - requestAnimationFrame is scheduled OUTSIDE the setState updater.  Calling
 *   rAF inside an updater violates React's "updaters must be pure" rule and
 *   causes React 18 Strict Mode to double-schedule frames (each tick spawns
 *   two RAF callbacks), making the animation run at 2× speed and content
 *   appear as an instant block dump rather than a smooth stream.
 *
 * Returns { text, isTyping }:
 *   text      — the currently-visible slice of content
 *   isTyping  — true while the backend is streaming OR the animation is draining
 */
export function useStreamingText(
  content: string,
  isStreaming: boolean,
): { text: string; isTyping: boolean } {
  const [displayLen, setDisplayLen] = useState<number>(() =>
    isStreaming ? 0 : Infinity,
  );

  const contentRef      = useRef(content);
  const isStreamingRef  = useRef(isStreaming);
  const displayLenRef   = useRef<number>(isStreaming ? 0 : Infinity);
  const rafRef          = useRef<number | null>(null);
  const runningRef      = useRef(false);

  // Keep refs current so the RAF loop always sees the latest values without
  // re-registering effects or invalidating closures.
  contentRef.current     = content;
  isStreamingRef.current = isStreaming;

  useEffect(() => {
    if (!isStreaming) {
      // Stream ended.  If animation is still draining, let it finish naturally;
      // the loop will call setDisplayLen(Infinity) once it catches up.
      // If no animation is running, snap immediately.
      if (!runningRef.current) {
        displayLenRef.current = Infinity;
        setDisplayLen(Infinity);
      }
      return;
    }

    // New stream starting — reset position to 0 and begin the reveal loop.
    displayLenRef.current = 0;
    setDisplayLen(0);

    if (runningRef.current) return; // guard against double-start (Strict Mode)
    runningRef.current = true;

    const tick = () => {
      if (!runningRef.current) return;

      const target = contentRef.current.length;
      const prev   = displayLenRef.current;

      if (prev >= target) {
        // Caught up with what the backend has sent so far.
        if (isStreamingRef.current) {
          // More content still coming — keep the loop alive.
          rafRef.current = requestAnimationFrame(tick);
        } else {
          // Backend is also done — stop and snap to full.
          runningRef.current = false;
          rafRef.current     = null;
          displayLenRef.current = Infinity;
          setDisplayLen(Infinity);
        }
        return;
      }

      const next        = Math.min(prev + CHARS_PER_FRAME, target);
      const reachedEnd  = next >= target;
      const backendDone = !isStreamingRef.current;

      // Update position ref BEFORE setState so the next tick reads the right value.
      displayLenRef.current = next;
      // Pure setState call — no side effects inside the updater.
      setDisplayLen(next);

      if (!reachedEnd || !backendDone) {
        // Schedule next frame OUTSIDE the setState call.
        rafRef.current = requestAnimationFrame(tick);
      } else {
        // Both caught up AND backend done — finish on next frame to avoid flicker.
        runningRef.current = false;
        rafRef.current = requestAnimationFrame(() => {
          displayLenRef.current = Infinity;
          setDisplayLen(Infinity);
        });
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming]);

  // Cancel animation on unmount.
  useEffect(() => {
    return () => {
      runningRef.current = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  const text =
    displayLen === Infinity
      ? content
      : content.slice(0, Math.min(displayLen, content.length));

  const isTyping =
    isStreaming || (displayLen !== Infinity && displayLen < content.length);

  return { text, isTyping };
}
