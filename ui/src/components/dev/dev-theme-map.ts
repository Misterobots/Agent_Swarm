/**
 * dev-theme-map.ts
 * Maps Memex ChatTheme IDs to Monaco editor themes and xterm terminal palettes.
 * All non-"memex-light" Memex themes are dark; only "memex" with light mode
 * (themeMode=light) produces a light editor.
 */

import type { ChatTheme } from "@/lib/stores/settings-store";

// ---------------------------------------------------------------------------
// Monaco theme registration
// ---------------------------------------------------------------------------

let _monacoThemesRegistered = false;

/**
 * Call once (inside a useEffect with empty deps) to register custom Monaco
 * themes.  Safe to call multiple times — subsequent calls are no-ops.
 */
export async function registerMonacoThemes(): Promise<void> {
  if (_monacoThemesRegistered) return;
  _monacoThemesRegistered = true;

  // @monaco-editor/react ships Monaco as a bundled dependency; use its loader
  // to get the monaco instance rather than importing monaco-editor directly.
  const { loader } = await import("@monaco-editor/react");
  const monaco = await loader.init();

  // memex-dark — neutral zinc surfaces, teal accent
  monaco.editor.defineTheme("memex-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "8b8b94", fontStyle: "italic" },
      { token: "keyword", foreground: "00CCA8" },
      { token: "string", foreground: "9580FF" },
      { token: "number", foreground: "00EED0" },
      { token: "type", foreground: "00CCA8" },
    ],
    colors: {
      "editor.background": "#0a0a0d",
      "editor.foreground": "#ededf0",
      "editor.lineHighlightBackground": "#16161a",
      "editorLineNumber.foreground": "#5b5b66",
      "editorLineNumber.activeForeground": "#8b8b94",
      "editor.selectionBackground": "#00CCA830",
      "editor.inactiveSelectionBackground": "#00CCA818",
      "editorCursor.foreground": "#00CCA8",
      "editorIndentGuide.background1": "#26262b",
      "editorIndentGuide.activeBackground1": "#00CCA844",
      "editor.findMatchBackground": "#00CCA840",
      "editor.findMatchHighlightBackground": "#00CCA820",
      "editorWidget.background": "#111114",
      "editorWidget.border": "#26262b",
      "editorSuggestWidget.background": "#16161a",
      "editorSuggestWidget.border": "#26262b",
      "editorSuggestWidget.selectedBackground": "#00CCA818",
      "scrollbarSlider.background": "#26262b80",
      "scrollbarSlider.hoverBackground": "#26262bcc",
      "scrollbarSlider.activeBackground": "#00CCA840",
    },
  });

  // memex-light — clean neutral whites, teal accent
  monaco.editor.defineTheme("memex-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment", foreground: "9696a3", fontStyle: "italic" },
      { token: "keyword", foreground: "009984" },
      { token: "string", foreground: "7c6fcd" },
      { token: "number", foreground: "007d6b" },
      { token: "type", foreground: "009984" },
    ],
    colors: {
      "editor.background": "#f8f8fa",
      "editor.foreground": "#1a1a1f",
      "editor.lineHighlightBackground": "#f1f1f4",
      "editorLineNumber.foreground": "#9696a3",
      "editorLineNumber.activeForeground": "#6b6b78",
      "editor.selectionBackground": "#00998430",
      "editor.inactiveSelectionBackground": "#00998418",
      "editorCursor.foreground": "#009984",
      "editorIndentGuide.background1": "#e4e4e9",
      "editorIndentGuide.activeBackground1": "#00998440",
      "editor.findMatchBackground": "#00998440",
      "editor.findMatchHighlightBackground": "#00998820",
      "editorWidget.background": "#ffffff",
      "editorWidget.border": "#e4e4e9",
      "editorSuggestWidget.background": "#f1f1f4",
      "editorSuggestWidget.border": "#e4e4e9",
      "editorSuggestWidget.selectedBackground": "#00998418",
      "scrollbarSlider.background": "#e4e4e980",
      "scrollbarSlider.hoverBackground": "#e4e4e9cc",
      "scrollbarSlider.activeBackground": "#00998440",
    },
  });

  // lcars — LCARS amber/purple palette
  monaco.editor.defineTheme("memex-lcars", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "8c66ff", fontStyle: "italic" },
      { token: "keyword", foreground: "cc99ff" },
      { token: "string", foreground: "e67399" },
      { token: "number", foreground: "ffdd00" },
      { token: "type", foreground: "e6d9ff" },
    ],
    colors: {
      "editor.background": "#090514",
      "editor.foreground": "#e6d9ff",
      "editor.lineHighlightBackground": "#1d1040",
      "editorLineNumber.foreground": "#8c66ff",
      "editorLineNumber.activeForeground": "#b399ff",
      "editor.selectionBackground": "#cc99ff30",
      "editor.inactiveSelectionBackground": "#cc99ff18",
      "editorCursor.foreground": "#cc99ff",
      "editorIndentGuide.background1": "#7a5cbf",
      "editorWidget.background": "#130a2a",
      "editorWidget.border": "#7a5cbf",
      "editorSuggestWidget.background": "#1d1040",
      "editorSuggestWidget.border": "#7a5cbf",
      "editorSuggestWidget.selectedBackground": "#cc99ff20",
      "scrollbarSlider.background": "#7a5cbf80",
      "scrollbarSlider.hoverBackground": "#cc99ffcc",
      "scrollbarSlider.activeBackground": "#cc99ff40",
    },
  });

  // lcars-blue — TNG pale blue/periwinkle
  monaco.editor.defineTheme("memex-lcars-blue", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "334477", fontStyle: "italic" },
      { token: "keyword", foreground: "88AAEE" },
      { token: "string", foreground: "CC99FF" },
      { token: "number", foreground: "AABBEE" },
      { token: "type", foreground: "BBCCFF" },
    ],
    colors: {
      "editor.background": "#000008",
      "editor.foreground": "#BBCCFF",
      "editor.lineHighlightBackground": "#0C0E1E",
      "editorLineNumber.foreground": "#334477",
      "editorLineNumber.activeForeground": "#6677BB",
      "editor.selectionBackground": "#88AAEE30",
      "editor.inactiveSelectionBackground": "#88AAEE18",
      "editorCursor.foreground": "#88AAEE",
      "editorIndentGuide.background1": "#3344AA",
      "editorWidget.background": "#06070F",
      "editorWidget.border": "#3344AA",
      "scrollbarSlider.background": "#3344AA80",
      "scrollbarSlider.hoverBackground": "#88AAEEcc",
      "scrollbarSlider.activeBackground": "#88AAEE40",
    },
  });

  // lcars-teal — cyan-teal palette
  monaco.editor.defineTheme("memex-lcars-teal", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "226677", fontStyle: "italic" },
      { token: "keyword", foreground: "00CCDD" },
      { token: "string", foreground: "FF7700" },
      { token: "number", foreground: "44DDEE" },
      { token: "type", foreground: "AAEEFF" },
    ],
    colors: {
      "editor.background": "#000C0E",
      "editor.foreground": "#AAEEFF",
      "editor.lineHighlightBackground": "#081E22",
      "editorLineNumber.foreground": "#226677",
      "editorLineNumber.activeForeground": "#449999",
      "editor.selectionBackground": "#00CCDD30",
      "editor.inactiveSelectionBackground": "#00CCDD18",
      "editorCursor.foreground": "#00CCDD",
      "editorIndentGuide.background1": "#1A7788",
      "editorWidget.background": "#041214",
      "editorWidget.border": "#1A7788",
      "scrollbarSlider.background": "#1A778880",
      "scrollbarSlider.hoverBackground": "#00CCDDcc",
      "scrollbarSlider.activeBackground": "#00CCDD40",
    },
  });

  // cyberpunk — matrix teal/magenta
  monaco.editor.defineTheme("memex-cyberpunk", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "2A5045", fontStyle: "italic" },
      { token: "keyword", foreground: "00DDC0" },
      { token: "string", foreground: "CC44FF" },
      { token: "number", foreground: "55FFDD" },
      { token: "type", foreground: "C8FFF0" },
    ],
    colors: {
      "editor.background": "#020C0A",
      "editor.foreground": "#C8FFF0",
      "editor.lineHighlightBackground": "#0A1A16",
      "editorLineNumber.foreground": "#2A5045",
      "editorLineNumber.activeForeground": "#4D9980",
      "editor.selectionBackground": "#00DDC030",
      "editor.inactiveSelectionBackground": "#00DDC018",
      "editorCursor.foreground": "#00DDC0",
      "editorIndentGuide.background1": "#1C5A48",
      "editorWidget.background": "#050F0D",
      "editorWidget.border": "#1C5A48",
      "scrollbarSlider.background": "#1C5A4880",
      "scrollbarSlider.hoverBackground": "#00DDC0cc",
      "scrollbarSlider.activeBackground": "#00DDC040",
    },
  });

  // shadowrun — deep teal-black, teal accent
  monaco.editor.defineTheme("memex-shadowrun", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "225544", fontStyle: "italic" },
      { token: "keyword", foreground: "00DDC0" },
      { token: "string", foreground: "CC44FF" },
      { token: "number", foreground: "55FFDD" },
      { token: "type", foreground: "C8FFF0" },
    ],
    colors: {
      "editor.background": "#020C0A",
      "editor.foreground": "#C8FFF0",
      "editor.lineHighlightBackground": "#102420",
      "editorLineNumber.foreground": "#225544",
      "editorLineNumber.activeForeground": "#3E8070",
      "editor.selectionBackground": "#00DDC030",
      "editor.inactiveSelectionBackground": "#00DDC018",
      "editorCursor.foreground": "#00DDC0",
      "editorIndentGuide.background1": "#1A5040",
      "editorWidget.background": "#050F0D",
      "editorWidget.border": "#1A5040",
      "scrollbarSlider.background": "#1A504080",
      "scrollbarSlider.hoverBackground": "#00DDC0cc",
      "scrollbarSlider.activeBackground": "#00DDC040",
    },
  });

  // ops — tactical mission-control blue
  monaco.editor.defineTheme("memex-ops", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "263C5C", fontStyle: "italic" },
      { token: "keyword", foreground: "4C9FE8" },
      { token: "string", foreground: "E05C4C" },
      { token: "number", foreground: "7EC0FF" },
      { token: "type", foreground: "BED0EE" },
    ],
    colors: {
      "editor.background": "#050C1A",
      "editor.foreground": "#BED0EE",
      "editor.lineHighlightBackground": "#0E1B34",
      "editorLineNumber.foreground": "#263C5C",
      "editorLineNumber.activeForeground": "#446688",
      "editor.selectionBackground": "#4C9FE830",
      "editor.inactiveSelectionBackground": "#4C9FE818",
      "editorCursor.foreground": "#4C9FE8",
      "editorIndentGuide.background1": "#1A2E50",
      "editorWidget.background": "#0A1328",
      "editorWidget.border": "#1A2E50",
      "scrollbarSlider.background": "#1A2E5080",
      "scrollbarSlider.hoverBackground": "#4C9FE8cc",
      "scrollbarSlider.activeBackground": "#4C9FE840",
    },
  });

  // terminal — phosphor green CRT
  monaco.editor.defineTheme("memex-terminal", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "125522", fontStyle: "italic" },
      { token: "keyword", foreground: "33FF66" },
      { token: "string", foreground: "FFAA33" },
      { token: "number", foreground: "66FF99" },
      { token: "type", foreground: "33FF66" },
    ],
    colors: {
      "editor.background": "#010601",
      "editor.foreground": "#33FF66",
      "editor.lineHighlightBackground": "#030E03",
      "editorLineNumber.foreground": "#125522",
      "editorLineNumber.activeForeground": "#1D8833",
      "editor.selectionBackground": "#33FF6630",
      "editor.inactiveSelectionBackground": "#33FF6618",
      "editorCursor.foreground": "#33FF66",
      "editorIndentGuide.background1": "#164416",
      "editorWidget.background": "#020A02",
      "editorWidget.border": "#164416",
      "scrollbarSlider.background": "#16441680",
      "scrollbarSlider.hoverBackground": "#33FF66cc",
      "scrollbarSlider.activeBackground": "#33FF6640",
    },
  });

  // hal9000 — deep red
  monaco.editor.defineTheme("memex-hal9000", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "3A1818", fontStyle: "italic" },
      { token: "keyword", foreground: "CC0000" },
      { token: "string", foreground: "880000" },
      { token: "number", foreground: "FF2020" },
      { token: "type", foreground: "E0D8D8" },
    ],
    colors: {
      "editor.background": "#000001",
      "editor.foreground": "#E0D8D8",
      "editor.lineHighlightBackground": "#080005",
      "editorLineNumber.foreground": "#3A1818",
      "editorLineNumber.activeForeground": "#6A5050",
      "editor.selectionBackground": "#CC000030",
      "editor.inactiveSelectionBackground": "#CC000018",
      "editorCursor.foreground": "#CC0000",
      "editorIndentGuide.background1": "#180000",
      "editorWidget.background": "#040002",
      "editorWidget.border": "#3A1818",
      "scrollbarSlider.background": "#18000080",
      "scrollbarSlider.hoverBackground": "#CC0000cc",
      "scrollbarSlider.activeBackground": "#CC000040",
    },
  });

  // nostromo — amber distress
  monaco.editor.defineTheme("memex-nostromo", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "664400", fontStyle: "italic" },
      { token: "keyword", foreground: "FF8C00" },
      { token: "string", foreground: "FFAA33" },
      { token: "number", foreground: "FFC870" },
      { token: "type", foreground: "FFC870" },
    ],
    colors: {
      "editor.background": "#060400",
      "editor.foreground": "#FFC870",
      "editor.lineHighlightBackground": "#140D00",
      "editorLineNumber.foreground": "#664400",
      "editorLineNumber.activeForeground": "#AA6622",
      "editor.selectionBackground": "#FF8C0030",
      "editor.inactiveSelectionBackground": "#FF8C0018",
      "editorCursor.foreground": "#FF8C00",
      "editorIndentGuide.background1": "#281800",
      "editorWidget.background": "#0C0800",
      "editorWidget.border": "#281800",
      "scrollbarSlider.background": "#28180080",
      "scrollbarSlider.hoverBackground": "#FF8C00cc",
      "scrollbarSlider.activeBackground": "#FF8C0040",
    },
  });

  // tron — electric cyan
  monaco.editor.defineTheme("memex-tron", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "183C50", fontStyle: "italic" },
      { token: "keyword", foreground: "00D8FF" },
      { token: "string", foreground: "FF8C20" },
      { token: "number", foreground: "60EEFF" },
      { token: "type", foreground: "D0F0FF" },
    ],
    colors: {
      "editor.background": "#000508",
      "editor.foreground": "#D0F0FF",
      "editor.lineHighlightBackground": "#041420",
      "editorLineNumber.foreground": "#183C50",
      "editorLineNumber.activeForeground": "#3A8AAA",
      "editor.selectionBackground": "#00D8FF30",
      "editor.inactiveSelectionBackground": "#00D8FF18",
      "editorCursor.foreground": "#00D8FF",
      "editorIndentGuide.background1": "#1A3C50",
      "editorWidget.background": "#020C14",
      "editorWidget.border": "#1A3C50",
      "scrollbarSlider.background": "#1A3C5080",
      "scrollbarSlider.hoverBackground": "#00D8FFcc",
      "scrollbarSlider.activeBackground": "#00D8FF40",
    },
  });

  // bladerunner — Voigt-Kampff amber
  monaco.editor.defineTheme("memex-bladerunner", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "5A3818", fontStyle: "italic" },
      { token: "keyword", foreground: "DC940E" },
      { token: "string", foreground: "FF5E1A" },
      { token: "number", foreground: "FF9A20" },
      { token: "type", foreground: "F0D4A0" },
    ],
    colors: {
      "editor.background": "#060200",
      "editor.foreground": "#F0D4A0",
      "editor.lineHighlightBackground": "#160A00",
      "editorLineNumber.foreground": "#5A3818",
      "editorLineNumber.activeForeground": "#8A6030",
      "editor.selectionBackground": "#DC940E30",
      "editor.inactiveSelectionBackground": "#DC940E18",
      "editorCursor.foreground": "#DC940E",
      "editorIndentGuide.background1": "#280E00",
      "editorWidget.background": "#0E0600",
      "editorWidget.border": "#280E00",
      "scrollbarSlider.background": "#280E0080",
      "scrollbarSlider.hoverBackground": "#DC940Ecc",
      "scrollbarSlider.activeBackground": "#DC940E40",
    },
  });

  // dune — Arrakis spice desert
  monaco.editor.defineTheme("memex-dune", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "604820", fontStyle: "italic" },
      { token: "keyword", foreground: "E8881A" },
      { token: "string", foreground: "F0A840" },
      { token: "number", foreground: "F0D898" },
      { token: "type", foreground: "F0D898" },
    ],
    colors: {
      "editor.background": "#0E0700",
      "editor.foreground": "#F0D898",
      "editor.lineHighlightBackground": "#221400",
      "editorLineNumber.foreground": "#604820",
      "editorLineNumber.activeForeground": "#A07840",
      "editor.selectionBackground": "#E8881A30",
      "editor.inactiveSelectionBackground": "#E8881A18",
      "editorCursor.foreground": "#E8881A",
      "editorIndentGuide.background1": "#301A00",
      "editorWidget.background": "#180E00",
      "editorWidget.border": "#301A00",
      "scrollbarSlider.background": "#301A0080",
      "scrollbarSlider.hoverBackground": "#E8881Acc",
      "scrollbarSlider.activeBackground": "#E8881A40",
    },
  });

  // memex-archive — sepia memory
  monaco.editor.defineTheme("memex-archive", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "5A4828", fontStyle: "italic" },
      { token: "keyword", foreground: "C8922A" },
      { token: "string", foreground: "D4A843" },
      { token: "number", foreground: "E8D8A8" },
      { token: "type", foreground: "E8D8A8" },
    ],
    colors: {
      "editor.background": "#0E0A02",
      "editor.foreground": "#E8D8A8",
      "editor.lineHighlightBackground": "#201808",
      "editorLineNumber.foreground": "#5A4828",
      "editorLineNumber.activeForeground": "#907848",
      "editor.selectionBackground": "#C8922A30",
      "editor.inactiveSelectionBackground": "#C8922A18",
      "editorCursor.foreground": "#C8922A",
      "editorIndentGuide.background1": "#30200A",
      "editorWidget.background": "#181208",
      "editorWidget.border": "#30200A",
      "scrollbarSlider.background": "#30200A80",
      "scrollbarSlider.hoverBackground": "#C8922Acc",
      "scrollbarSlider.activeBackground": "#C8922A40",
    },
  });
}

// ---------------------------------------------------------------------------
// Monaco theme name lookup
// ---------------------------------------------------------------------------

/**
 * Returns the Monaco theme name for a given Memex ChatTheme + light-mode flag.
 * Always returns a valid registered theme name (falls back to "memex-dark").
 */
export function getMonacoThemeName(themeId: ChatTheme, isLight = false): string {
  // memex in light mode is the only light theme
  if (themeId === "memex" && isLight) return "memex-light";

  switch (themeId) {
    case "memex":         return "memex-dark";
    case "lcars":         return "memex-lcars";
    case "lcars-blue":    return "memex-lcars-blue";
    case "lcars-teal":    return "memex-lcars-teal";
    case "cyberpunk":     return "memex-cyberpunk";
    case "shadowrun":     return "memex-shadowrun";
    case "ops":           return "memex-ops";
    case "terminal":      return "memex-terminal";
    case "hal9000":       return "memex-hal9000";
    case "nostromo":      return "memex-nostromo";
    case "tron":          return "memex-tron";
    case "bladerunner":   return "memex-bladerunner";
    case "dune":          return "memex-dune";
    case "memex-archive": return "memex-archive";
    default:              return "memex-dark";
  }
}

// ---------------------------------------------------------------------------
// xterm theme lookup
// ---------------------------------------------------------------------------

interface XtermTheme {
  background: string;
  foreground: string;
  cursor: string;
  cursorAccent?: string;
  selectionBackground?: string;
  selectionForeground?: string;
  black: string;
  red: string;
  green: string;
  yellow: string;
  blue: string;
  magenta: string;
  cyan: string;
  white: string;
  brightBlack: string;
  brightRed: string;
  brightGreen: string;
  brightYellow: string;
  brightBlue: string;
  brightMagenta: string;
  brightCyan: string;
  brightWhite: string;
}

// Shared ANSI base palette that works across dark themes — overridden per-theme
// only where the theme calls for distinctly different colours.
const ANSI_DARK_BASE: Omit<XtermTheme, "background" | "foreground" | "cursor" | "selectionBackground"> = {
  black: "#18181b",
  red: "#ef4444",
  green: "#10b981",
  yellow: "#f59e0b",
  blue: "#3b82f6",
  magenta: "#a855f7",
  cyan: "#22d3ee",
  white: "#e4e4e7",
  brightBlack: "#52525b",
  brightRed: "#f87171",
  brightGreen: "#34d399",
  brightYellow: "#fbbf24",
  brightBlue: "#60a5fa",
  brightMagenta: "#c084fc",
  brightCyan: "#67e8f9",
  brightWhite: "#fafafa",
};

/**
 * Returns an xterm-compatible ITheme object for the given Memex ChatTheme.
 */
export function getXtermTheme(themeId: ChatTheme, isLight = false): XtermTheme {
  // memex light
  if (themeId === "memex" && isLight) {
    return {
      background: "#f8f8fa",
      foreground: "#1a1a1f",
      cursor: "#009984",
      selectionBackground: "#00998430",
      black: "#1a1a1f",
      red: "#dc2626",
      green: "#059669",
      yellow: "#d97706",
      blue: "#2563eb",
      magenta: "#7c3aed",
      cyan: "#0891b2",
      white: "#f8f8fa",
      brightBlack: "#6b6b78",
      brightRed: "#ef4444",
      brightGreen: "#10b981",
      brightYellow: "#f59e0b",
      brightBlue: "#3b82f6",
      brightMagenta: "#a855f7",
      brightCyan: "#22d3ee",
      brightWhite: "#ffffff",
    };
  }

  switch (themeId) {
    case "memex":
    default:
      return {
        background: "#0a0a0d",
        foreground: "#ededf0",
        cursor: "#00CCA8",
        selectionBackground: "#00CCA830",
        ...ANSI_DARK_BASE,
        cyan: "#00CCA8",
        brightCyan: "#00EED0",
      };

    case "lcars":
      return {
        background: "#090514",
        foreground: "#e6d9ff",
        cursor: "#cc99ff",
        selectionBackground: "#cc99ff30",
        ...ANSI_DARK_BASE,
        magenta: "#cc99ff",
        brightMagenta: "#e6ccff",
        yellow: "#ffdd00",
        brightYellow: "#ffe866",
      };

    case "lcars-blue":
      return {
        background: "#000008",
        foreground: "#BBCCFF",
        cursor: "#88AAEE",
        selectionBackground: "#88AAEE30",
        ...ANSI_DARK_BASE,
        blue: "#88AAEE",
        brightBlue: "#BBCCFF",
        magenta: "#CC99FF",
        brightMagenta: "#DDB9FF",
      };

    case "lcars-teal":
      return {
        background: "#000C0E",
        foreground: "#AAEEFF",
        cursor: "#00CCDD",
        selectionBackground: "#00CCDD30",
        ...ANSI_DARK_BASE,
        cyan: "#00CCDD",
        brightCyan: "#55EEFF",
        green: "#00CC77",
        brightGreen: "#33EE99",
      };

    case "cyberpunk":
    case "shadowrun":
      return {
        background: "#020C0A",
        foreground: "#C8FFF0",
        cursor: "#00DDC0",
        selectionBackground: "#00DDC030",
        ...ANSI_DARK_BASE,
        cyan: "#00DDC0",
        brightCyan: "#55FFDD",
        magenta: "#CC44FF",
        brightMagenta: "#DD77FF",
      };

    case "ops":
      return {
        background: "#050C1A",
        foreground: "#BED0EE",
        cursor: "#4C9FE8",
        selectionBackground: "#4C9FE830",
        ...ANSI_DARK_BASE,
        blue: "#4C9FE8",
        brightBlue: "#7EC0FF",
        red: "#E05C4C",
        brightRed: "#FF7060",
      };

    case "terminal":
      return {
        background: "#010601",
        foreground: "#33FF66",
        cursor: "#33FF66",
        selectionBackground: "#33FF6630",
        ...ANSI_DARK_BASE,
        green: "#33FF66",
        brightGreen: "#66FF99",
        yellow: "#FFAA33",
        brightYellow: "#FFCC55",
        black: "#010601",
        brightBlack: "#164416",
      };

    case "hal9000":
      return {
        background: "#000001",
        foreground: "#E0D8D8",
        cursor: "#CC0000",
        selectionBackground: "#CC000030",
        ...ANSI_DARK_BASE,
        red: "#CC0000",
        brightRed: "#FF2020",
        black: "#000001",
        brightBlack: "#3A1818",
      };

    case "nostromo":
      return {
        background: "#060400",
        foreground: "#FFC870",
        cursor: "#FF8C00",
        selectionBackground: "#FF8C0030",
        ...ANSI_DARK_BASE,
        yellow: "#FF8C00",
        brightYellow: "#FFAA33",
        white: "#FFC870",
        brightWhite: "#FFE0A0",
      };

    case "tron":
      return {
        background: "#000508",
        foreground: "#D0F0FF",
        cursor: "#00D8FF",
        selectionBackground: "#00D8FF30",
        ...ANSI_DARK_BASE,
        cyan: "#00D8FF",
        brightCyan: "#60EEFF",
        magenta: "#FF8C20",
        brightMagenta: "#FFA840",
      };

    case "bladerunner":
      return {
        background: "#060200",
        foreground: "#F0D4A0",
        cursor: "#DC940E",
        selectionBackground: "#DC940E30",
        ...ANSI_DARK_BASE,
        yellow: "#DC940E",
        brightYellow: "#FF9A20",
        red: "#FF5E1A",
        brightRed: "#FF7A40",
      };

    case "dune":
      return {
        background: "#0E0700",
        foreground: "#F0D898",
        cursor: "#E8881A",
        selectionBackground: "#E8881A30",
        ...ANSI_DARK_BASE,
        yellow: "#E8881A",
        brightYellow: "#F0A840",
        white: "#F0D898",
        brightWhite: "#F8ECC8",
      };

    case "memex-archive":
      return {
        background: "#0E0A02",
        foreground: "#E8D8A8",
        cursor: "#C8922A",
        selectionBackground: "#C8922A30",
        ...ANSI_DARK_BASE,
        yellow: "#C8922A",
        brightYellow: "#D4A843",
        white: "#E8D8A8",
        brightWhite: "#F0E8C8",
      };
  }
}
