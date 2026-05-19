"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

export interface PalaceColorTokens {
  bg: string;
  surface: string;
  panel: string;
  border: string;
  text: string;
  muted: string;
  accent: string;
  accentStrong: string;
  accent2: string;
  themeName: string;
  isLight: boolean;
  skyTop: string;
  skyBottom: string;
  mist: string;
  glowSoft: string;
  trim: string;
  shadow: string;
  highlight: string;
  floorEdge: string;
  archCurve: number;
  bannerOpacity: number;
  particleCount: number;
  motif: "forge" | "slab" | "signal" | "grid" | "terminal" | "lcars" | "neon" | "gallery";
}

type PalaceMotif = PalaceColorTokens["motif"];
type PalaceMotifConfig = { motif: PalaceMotif; archCurve: number; bannerOpacity: number; particleCount: number };

const DEFAULT_MOTIF_CONFIG: PalaceMotifConfig = {
  motif: "slab",
  archCurve: 0.9,
  bannerOpacity: 0.1,
  particleCount: 18,
};

const THEME_MOTIF_CONFIG = {
  ember: { motif: "forge", archCurve: 1.08, bannerOpacity: 0.16, particleCount: 42 },
  slate: { motif: "slab", archCurve: 0.88, bannerOpacity: 0.12, particleCount: 20 },
  signal: { motif: "signal", archCurve: 0.94, bannerOpacity: 0.14, particleCount: 26 },
  office: { motif: "grid", archCurve: 0.82, bannerOpacity: 0.08, particleCount: 12 },
  hacker: { motif: "terminal", archCurve: 0.9, bannerOpacity: 0.14, particleCount: 32 },
  "star-trek": { motif: "lcars", archCurve: 1.18, bannerOpacity: 0.18, particleCount: 24 },
  cyberpunk: { motif: "neon", archCurve: 0.98, bannerOpacity: 0.2, particleCount: 36 },
  minimal: { motif: "gallery", archCurve: 0.74, bannerOpacity: 0.06, particleCount: 8 },
} satisfies Record<string, PalaceMotifConfig>;

/**
 * Reads the active Hive theme CSS variables and returns Three.js materials
 * that react to theme changes. Materials are re-created when the
 * `data-theme` attribute on <html> changes.
 */
export function usePalaceMaterials() {
  const ref = useRef<ReturnType<typeof buildMaterials> | null>(null);

  // Observe theme changes via MutationObserver on data-theme
  const theme = useThemeAttr();

  const materials = useMemo(() => {
    // Dispose old materials
    if (ref.current) {
      Object.values(ref.current).forEach((m) => {
        if (m instanceof THREE.Material) m.dispose();
      });
    }
    const m = buildMaterials();
    ref.current = m;
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  return materials;
}

/** Returns the raw CSS variable colors for use in lights / fog. */
export function usePalaceColors() {
  const theme = useThemeAttr();
  return useMemo(() => buildColorTokens(theme), [theme]);
}

// ── Internals ─────────────────────────────────────────────────────────────

function useThemeAttr() {
  const [theme, setTheme] = useState("");

  useEffect(() => {
    const el = document.documentElement;
    setTheme(el.getAttribute("data-theme") || "memex");

    const obs = new MutationObserver(() => {
      const next = el.getAttribute("data-theme") || "memex";
      setTheme((prev) => (prev !== next ? next : prev));
    });
    obs.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);

  return theme;
}

function cssVar(name: string): string {
  if (typeof window === "undefined") return "#888888";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888888";
}

function readColors() {
  return {
    bg: cssVar("--chat-bg"),
    surface: cssVar("--chat-surface"),
    panel: cssVar("--chat-panel"),
    border: cssVar("--chat-border"),
    text: cssVar("--chat-text"),
    muted: cssVar("--chat-muted"),
    accent: cssVar("--chat-accent"),
    accentStrong: cssVar("--chat-accent-strong"),
    accent2: cssVar("--chat-accent-2"),
  };
}

function mixColors(a: string, b: string, amount: number) {
  const color = new THREE.Color(a);
  color.lerp(new THREE.Color(b), amount);
  return `#${color.getHexString()}`;
}

function buildColorTokens(theme: string): PalaceColorTokens {
  const base = readColors();
  const mood = {
    ember: 0.28,
    slate: 0.14,
    signal: 0.18,
    office: 0.12,
    hacker: 0.24,
    "star-trek": 0.2,
    cyberpunk: 0.32,
    minimal: 0.1,
  }[theme] ?? 0.18;

  const motifMap = THEME_MOTIF_CONFIG[theme as keyof typeof THEME_MOTIF_CONFIG] ?? DEFAULT_MOTIF_CONFIG;

  const isLight = theme === "office" || theme === "minimal";

  return {
    ...base,
    themeName: theme,
    isLight,
    skyTop: mixColors(base.bg, base.accentStrong, mood + 0.08),
    skyBottom: mixColors(base.surface, base.bg, 0.45),
    mist: mixColors(base.accent, base.bg, 0.72),
    glowSoft: mixColors(base.accent, base.panel, 0.38),
    trim: mixColors(base.accent, base.border, 0.45),
    shadow: mixColors(base.bg, "#000000", 0.35),
    highlight: mixColors(base.accentStrong, "#ffffff", 0.26),
    floorEdge: mixColors(base.panel, base.accentStrong, 0.22),
    archCurve: motifMap.archCurve,
    bannerOpacity: motifMap.bannerOpacity,
    particleCount: motifMap.particleCount,
    motif: motifMap.motif,
  };
}

function buildMaterials() {
  const c = buildColorTokens(useThemeFallback());

  const wall = new THREE.MeshPhysicalMaterial({
    color: mixColors(c.surface, c.panel, 0.28),
    roughness: 0.52,
    metalness: 0.08,
    clearcoat: 0.18,
    clearcoatRoughness: 0.75,
    sheen: 0.2,
    sheenColor: new THREE.Color(c.glowSoft),
  });

  const floor = new THREE.MeshPhysicalMaterial({
    color: mixColors(c.panel, c.bg, 0.12),
    roughness: 0.36,
    metalness: 0.2,
    clearcoat: 0.9,
    clearcoatRoughness: 0.45,
    reflectivity: 0.55,
  });

  const accentMat = new THREE.MeshPhysicalMaterial({
    color: mixColors(c.accent, c.accentStrong, 0.14),
    roughness: 0.2,
    metalness: 0.62,
    clearcoat: 0.82,
    clearcoatRoughness: 0.24,
    emissive: c.accent,
    emissiveIntensity: 0.22,
  });

  const drawer = new THREE.MeshPhysicalMaterial({
    color: mixColors(c.border, c.panel, 0.3),
    roughness: 0.42,
    metalness: 0.3,
    clearcoat: 0.35,
    clearcoatRoughness: 0.5,
  });

  const drawerHighlight = new THREE.MeshPhysicalMaterial({
    color: c.accent,
    roughness: 0.18,
    metalness: 0.44,
    clearcoat: 0.65,
    clearcoatRoughness: 0.22,
    emissive: c.accentStrong,
    emissiveIntensity: 0.52,
  });

  const glow = new THREE.MeshPhysicalMaterial({
    color: c.accent,
    emissive: c.accent,
    emissiveIntensity: 0.75,
    transparent: true,
    opacity: 0.44,
    transmission: 0.08,
  });

  const text = new THREE.MeshPhysicalMaterial({
    color: c.text,
    roughness: 0.68,
    metalness: 0.02,
  });

  return { wall, floor, accent: accentMat, drawer, drawerHighlight, glow, text, colors: c };
}

function useThemeFallback() {
  if (typeof document === "undefined") return "ember";
  return document.documentElement.getAttribute("data-theme") || "memex";
}
