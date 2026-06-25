"use client";

import { useCallback, useReducer, useRef } from "react";

export type VimMode = "normal" | "insert";

interface VimState {
  mode:   VimMode;
  buffer: string; // pending key sequence in normal mode
}

type VimAction =
  | { type: "ENTER_INSERT" }
  | { type: "ENTER_NORMAL" }
  | { type: "KEY";    key: string }
  | { type: "RESET" };

function reducer(state: VimState, action: VimAction): VimState {
  switch (action.type) {
    case "ENTER_INSERT": return { mode: "insert",  buffer: "" };
    case "ENTER_NORMAL": return { mode: "normal",  buffer: "" };
    case "KEY":          return { ...state, buffer: state.buffer + action.key };
    case "RESET":        return { ...state, buffer: "" };
    default:             return state;
  }
}

export interface VimInputHandlers {
  mode:       VimMode;
  /** Attach to the textarea's onKeyDown */
  onKeyDown:  (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  /** Attach to the textarea's onKeyUp (for sequence reset) */
  onKeyUp:    (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
}

/**
 * Minimal Vim-mode for the chat textarea.
 *
 * Normal mode commands:
 *   i / a      → insert mode (i = before cursor, a = after)
 *   I          → insert at line start
 *   A          → insert at line end
 *   o          → new line below, insert
 *   dd         → clear entire input
 *   u          → undo (browser native Ctrl+Z)
 *   0 / ^      → start of line
 *   $          → end of line
 *   gg         → start of input
 *   G          → end of input
 *   w          → forward word
 *   b          → backward word
 *   Escape     → already normal, no-op
 *
 * Insert mode:
 *   Escape     → back to normal
 *   Everything else → native textarea behaviour
 */
export function useVimInput(
  textareaRef: React.RefObject<HTMLTextAreaElement>,
  onSubmit: () => void,
): VimInputHandlers {
  const [state, dispatch] = useReducer(reducer, { mode: "insert", buffer: "" });
  const bufferTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetBuffer = useCallback(() => {
    if (bufferTimer.current) clearTimeout(bufferTimer.current);
    bufferTimer.current = setTimeout(() => dispatch({ type: "RESET" }), 1000);
  }, []);

  const ta = () => textareaRef.current;

  const moveCursor = useCallback((pos: number) => {
    const el = ta();
    if (!el) return;
    el.setSelectionRange(pos, pos);
  }, []);

  const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const el = ta();
    if (!el) return;

    // --- INSERT MODE ---
    if (state.mode === "insert") {
      if (e.key === "Escape") {
        e.preventDefault();
        dispatch({ type: "ENTER_NORMAL" });
        // Move cursor back one (vim convention)
        const pos = Math.max(0, el.selectionStart - 1);
        moveCursor(pos);
      }
      return; // let all other keys pass through natively
    }

    // --- NORMAL MODE — intercept everything ---
    e.preventDefault();

    const text    = el.value;
    const cur     = el.selectionStart;
    const lineStart = text.lastIndexOf("\n", cur - 1) + 1;
    const nextNl    = text.indexOf("\n", cur);
    const lineEnd   = nextNl === -1 ? text.length : nextNl;

    const newBuffer = state.buffer + e.key;

    // Two-key sequences
    if (newBuffer === "dd") {
      el.value = "";
      el.dispatchEvent(new Event("input", { bubbles: true }));
      dispatch({ type: "RESET" });
      return;
    }
    if (newBuffer === "gg") {
      moveCursor(0);
      dispatch({ type: "RESET" });
      return;
    }

    // Single-key commands
    switch (e.key) {
      case "i":
        dispatch({ type: "ENTER_INSERT" });
        return;
      case "a":
        dispatch({ type: "ENTER_INSERT" });
        moveCursor(Math.min(cur + 1, text.length));
        return;
      case "I":
        dispatch({ type: "ENTER_INSERT" });
        moveCursor(lineStart);
        return;
      case "A":
        dispatch({ type: "ENTER_INSERT" });
        moveCursor(lineEnd);
        return;
      case "o": {
        dispatch({ type: "ENTER_INSERT" });
        const before = text.slice(0, lineEnd);
        const after  = text.slice(lineEnd);
        el.value = before + "\n" + after;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        moveCursor(lineEnd + 1);
        return;
      }
      case "G":
        moveCursor(text.length);
        dispatch({ type: "RESET" });
        return;
      case "0": case "^":
        moveCursor(lineStart);
        dispatch({ type: "RESET" });
        return;
      case "$":
        moveCursor(lineEnd);
        dispatch({ type: "RESET" });
        return;
      case "h":
        moveCursor(Math.max(lineStart, cur - 1));
        dispatch({ type: "RESET" });
        return;
      case "l":
        moveCursor(Math.min(lineEnd, cur + 1));
        dispatch({ type: "RESET" });
        return;
      case "j": {
        if (nextNl === -1) return;
        const col    = cur - lineStart;
        const nextLineEnd = text.indexOf("\n", nextNl + 1);
        const nextEnd = nextLineEnd === -1 ? text.length : nextLineEnd;
        moveCursor(Math.min(nextNl + 1 + col, nextEnd));
        dispatch({ type: "RESET" });
        return;
      }
      case "k": {
        const prevNl  = text.lastIndexOf("\n", lineStart - 2);
        if (prevNl === -1 && lineStart === 0) return;
        const prevStart = prevNl === -1 ? 0 : prevNl + 1;
        const col = cur - lineStart;
        moveCursor(Math.min(prevStart + col, lineStart - 1));
        dispatch({ type: "RESET" });
        return;
      }
      case "w": {
        const next = text.slice(cur).search(/\s\S/);
        moveCursor(next === -1 ? text.length : cur + next + 1);
        dispatch({ type: "RESET" });
        return;
      }
      case "b": {
        const prev = text.slice(0, cur).search(/\S\s[^\s]*$/);
        moveCursor(prev === -1 ? 0 : prev + 1);
        dispatch({ type: "RESET" });
        return;
      }
      case "u":
        document.execCommand("undo");
        dispatch({ type: "RESET" });
        return;
      case "Enter":
        onSubmit();
        dispatch({ type: "RESET" });
        return;
      default:
        // Start / extend buffer for multi-key sequences
        dispatch({ type: "KEY", key: e.key });
        resetBuffer();
    }
  }, [state.mode, state.buffer, moveCursor, onSubmit, resetBuffer]);

  const onKeyUp = useCallback(() => {
    // Buffer auto-resets via timer; nothing extra needed here
  }, []);

  return { mode: state.mode, onKeyDown, onKeyUp };
}
