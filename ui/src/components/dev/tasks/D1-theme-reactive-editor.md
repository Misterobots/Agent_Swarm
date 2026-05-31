# Task D1 — Theme-reactive editor + terminal

**Status:** Ready (no blockers)  
**Conflict zones touched:** `tabbed-editor.tsx`, `tabbed-terminal.tsx` (both owned by this task — claim before branching)  
**Estimated effort:** 2–3 hours  
**Dependencies:** none (pure UI, no backend)

---

## Problem

`tabbed-editor.tsx:273` hardcodes `theme="vs-dark"` on the Monaco editor. In
Memex light mode the editor is a black slab on a white UI; in LCARS/Dune/Tron
it clashes entirely.

`tabbed-terminal.tsx:152–174` hardcodes a full ANSI palette and
`tabbed-terminal.tsx:218` hardcodes `background: "#0a0a14"` on the xterm
container. Neither adapts to any of the 13 active Memex themes.

Both Monaco and xterm require a **JavaScript theme object** — they cannot read
CSS custom properties directly. The fix is to build that object by polling CSS
vars at mount and whenever the active theme changes.

---

## Implementation — Monaco (tabbed-editor.tsx)

### 1. Add the `useMonaco` hook and settings store subscription

```tsx
// At top of file, add imports:
import { useMonaco } from "@monaco-editor/react";
import { useSettingsStore } from "@/lib/stores/settings-store";
```

### 2. Add a CSS-var reader helper (add above the component, not inside)

```ts
function readVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim() || fallback;
}
```

### 3. Add a theme builder (add above the component)

```ts
function buildMonacoTheme(): Parameters<typeof import("monaco-editor").editor.defineTheme>[1] {
  const bg      = readVar("--chat-bg",      "#0a0a0d");
  const surface = readVar("--chat-surface", "#111114");
  const panel   = readVar("--chat-panel",   "#16161a");
  const border  = readVar("--chat-border",  "#26262b");
  const text    = readVar("--chat-text",    "#ededf0");
  const muted   = readVar("--chat-muted",   "#8b8b94");
  const subtle  = readVar("--chat-subtle",  "#5b5b66");
  const accent  = readVar("--chat-accent",  "#00CCA8");

  // Monaco colors must be #rrggbb or #rrggbbaa — no rgb() syntax.
  // CSS vars already return hex for all Memex themes.
  const accentDim = accent + "33"; // 20% alpha
  const accentSel = accent + "55"; // 33% alpha

  const isLight =
    document.documentElement.getAttribute("data-mode") === "light";

  return {
    base: isLight ? "vs" : "vs-dark",
    inherit: true,
    rules: [
      { token: "",             foreground: text.replace("#", "")   },
      { token: "comment",      foreground: subtle.replace("#", "") , fontStyle: "italic" },
      { token: "keyword",      foreground: accent.replace("#", ""), fontStyle: "bold"   },
      { token: "string",       foreground: accent.replace("#", "")                      },
      { token: "number",       foreground: muted.replace("#", "")                       },
      { token: "type",         foreground: accent.replace("#", "")                      },
      { token: "identifier",   foreground: text.replace("#", "")                        },
    ],
    colors: {
      "editor.background":                      bg,
      "editor.foreground":                      text,
      "editorLineNumber.foreground":            subtle,
      "editorLineNumber.activeForeground":      muted,
      "editor.lineHighlightBackground":         surface,
      "editor.selectionBackground":             accentSel,
      "editor.inactiveSelectionBackground":     accentDim,
      "editorCursor.foreground":                accent,
      "editorIndentGuide.background1":          border,
      "editorIndentGuide.activeBackground1":    muted,
      "editorWidget.background":                panel,
      "editorWidget.border":                    border,
      "editorSuggestWidget.background":         panel,
      "editorSuggestWidget.border":             border,
      "editorSuggestWidget.selectedBackground": surface,
      "input.background":                       surface,
      "input.border":                           border,
      "scrollbarSlider.background":             muted + "28",
      "scrollbarSlider.hoverBackground":        muted + "50",
      "scrollbarSlider.activeBackground":       accent + "50",
      "minimap.background":                     bg,
    },
  };
}
```

### 4. Wire it in the component

```tsx
export function TabbedEditor() {
  // Add these near the top of the component:
  const monaco = useMonaco();
  const theme     = useSettingsStore((s) => s.theme);
  const themeMode = useSettingsStore((s) => s.themeMode);

  // Define / update the Monaco theme whenever the Memex theme changes:
  useEffect(() => {
    if (!monaco) return;
    monaco.editor.defineTheme("memex-dynamic", buildMonacoTheme());
    monaco.editor.setTheme("memex-dynamic");
  }, [monaco, theme, themeMode]);

  // ... rest of existing state/hooks unchanged ...
```

### 5. Change the Editor component's `theme` prop

```tsx
// Before:
<Editor
  ...
  theme="vs-dark"
  ...
/>

// After:
<Editor
  ...
  theme="memex-dynamic"
  ...
/>
```

---

## Implementation — xterm (tabbed-terminal.tsx)

### 1. Add settings store import

```tsx
import { useSettingsStore } from "@/lib/stores/settings-store";
```

### 2. Add the same `readVar` helper (or import from a shared util if you extracted it above)

### 3. Add xterm theme builder (above component)

```ts
import type { ITheme } from "@xterm/xterm";

function buildXtermTheme(): ITheme {
  const bg     = readVar("--chat-bg",     "#0a0a0d");
  const fg     = readVar("--chat-text",   "#ededf0");
  const accent = readVar("--chat-accent", "#00CCA8");
  const muted  = readVar("--chat-muted",  "#8b8b94");
  const subtle = readVar("--chat-subtle", "#5b5b66");

  return {
    background:          bg,
    foreground:          fg,
    cursor:              accent,
    cursorAccent:        bg,
    selectionBackground: accent + "44",
    black:               bg,
    red:                 "#ef4444",
    green:               accent,   // theme accent as "success"
    yellow:              "#f59e0b",
    blue:                "#3b82f6",
    magenta:             "#a855f7",
    cyan:                accent,
    white:               fg,
    brightBlack:         subtle,
    brightRed:           "#f87171",
    brightGreen:         accent,
    brightYellow:        "#fbbf24",
    brightBlue:          "#60a5fa",
    brightMagenta:       "#c084fc",
    brightCyan:          accent,
    brightWhite:         "#fafafa",
  };
}
```

### 4. Subscribe to theme changes and push to live terminals

```tsx
export function TabbedTerminal() {
  const theme     = useSettingsStore((s) => s.theme);
  const themeMode = useSettingsStore((s) => s.themeMode);

  // Push updated theme to all live xterm instances:
  useEffect(() => {
    const xtermTheme = buildXtermTheme();
    setTabs((prev) =>
      prev.map((tab) => {
        if (tab.term) {
          tab.term.options.theme = xtermTheme;
        }
        return tab;
      })
    );
  }, [theme, themeMode]);

  // ... rest unchanged ...
```

### 5. Use the dynamic theme in `initTerminal`

```ts
// Inside the Terminal constructor call:
const term = new Terminal({
  cursorBlink: true,
  fontSize: 13,
  fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
  theme: buildXtermTheme(),   // ← was a hardcoded object
});
```

### 6. Remove the hardcoded background from the container div

```tsx
// Before (line ~218):
<div className="flex flex-col h-full bg-[#0a0a14]">

// After:
<div className="flex flex-col h-full bg-[var(--chat-bg)]">
```

---

## Notes / gotchas

- `readVar` must run in the browser — it's called inside `useEffect` and event
  handlers so this is safe. The `typeof document === "undefined"` guard handles
  SSR.
- Monaco's `defineTheme` is idempotent for the same name — calling it on every
  theme change is fine; it replaces the previous definition.
- xterm's `options.theme` setter triggers a full repaint on the next frame —
  no terminal restart needed.
- The `base: isLight ? "vs" : "vs-dark"` line ensures Monaco's built-in token
  coloring heuristics start from the right baseline. `inherit: true` means only
  the colors you explicitly override change.
- If `@xterm/xterm` doesn't export `ITheme` directly, import it as:
  `import type { ITheme } from "@xterm/xterm/src/common/services/Services"` or
  just use `Record<string, string>` as the type.

---

## Acceptance criteria

- [ ] In Memex dark theme: editor and terminal have a near-black background
  matching `--chat-bg`, teal accent cursor, readable text
- [ ] In Memex light theme: editor background is `#f8f8fa`, not black
- [ ] Switching themes in the sidebar theme picker updates both panels without
  a page reload
- [ ] In LCARS theme: purple accent drives cursor and keyword highlights
- [ ] No TypeScript errors
- [ ] `npm run build` completes cleanly
