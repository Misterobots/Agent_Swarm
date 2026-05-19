"use client";

import { useEffect, useRef, useState } from "react";

/** Characters revealed per animation frame (~60 fps → ~360 chars/sec) */
const CHARS_PER_FRAME = 6;

/**
 * Smoothly reveals text at a natural streaming cadence regardless of whether
 * the backend sends content in tiny trickles or large batches.
 *
 * Returns { text, isTyping }:
 *   text      — the currently-visible slice of content
 *   isTyping  — true while the backend is streaming OR the animation is still draining
 */
export function useStreamingText(
  content: string,
  isStreaming: boolean,
): { text: string; isTyping: boolean } {
  // Infinity = "show everything" for non-streaming (historical) messages
  const [displayLen, setDisplayLen] = useState<number>(() =>
    isStreaming ? 0 : Infinity,
  );

  const contentRef = useRef(content);
  const isStreamingRef = useRef(isStreaming);
  const rafRef = useRef<number | null>(null);
  const runningRef = useRef(false);

  // Keep refs current so the RAF loop always sees latest values
  contentRef.current = content;
  isStreamingRef.current = isStreaming;

  useEffect(() => {
    if (!isStreaming) {
      // Backend finished. If no animation is running, snap to full content.
      // If the animation IS running, it will drain naturally and stop.
      if (!runningRef.current) {
        setDisplayLen(Infinity);
      }
      return;
    }

    // New stream — reset position and start the reveal loop
    setDisplayLen(0);
    if (runningRef.current) return; // guard against double-start
    runningRef.current = true;

    const tick = () => {
      if (!runningRef.current) return;

      setDisplayLen((prev) => {
        const target = contentRef.current.length;

        if (prev >= target) {
          // Caught up with what the backend has sent so far
          if (isStreamingRef.current) {
            // More content is still coming — keep ticking
            rafRef.current = requestAnimationFrame(tick);
          } else {
            // Backend is also done — stop
            runningRef.current = false;
            rafRef.current = null;
          }
          return prev;
        }

        const next = Math.min(prev + CHARS_PER_FRAME, target);
        const reachedEnd = next >= target;
        const backendDone = !isStreamingRef.current;

        if (!reachedEnd || !backendDone) {
          rafRef.current = requestAnimationFrame(tick);
        } else {
          runningRef.current = false;
          rafRef.current = null;
        }

        return next;
      });
    };

    rafRef.current = requestAnimationFrame(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming]); // only react to streaming start/stop

  // Cancel on unmount
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
