"use client";

/**
 * Pioneer portraits — full-color clipart busts, one per named pioneer.
 *
 * Keyed by the short pioneer_name emitted by the backend (lowercased).
 * Fixed-color "photo ID" portraits on a light background — the role accent
 * lives on the card frame (border + foil stripe), not the portrait. A
 * role→primary fallback keeps role-only callers (and unnamed perspective
 * workers) rendering a real face.
 *
 * Feature-placement convention (keeps faces consistent):
 *   - eyes symmetric about the face centerline (cx 32 / cx 48), at the
 *     vertical middle of the face ellipse
 *   - glasses centered on the eyes with a real bridge gap (lenses never touch)
 *   - nose = a subtle base curve below the eyes (not a full ridge line)
 *   - mouth in the lower third
 *
 * viewBox is 0 0 80 96 (passport ratio). Each portrait fills its container.
 */

import * as React from "react";

/**
 * Renders the generated portrait (ComfyUI flat-vector bust, /public/pioneers/*.png)
 * for the pioneer, falling back to the hand-drawn SVG bust if the image is missing
 * or fails to load (offline / not-yet-generated perspective figures).
 */
export function PioneerPortrait({ name, role }: { name?: string; role?: string }) {
  const key = name?.toLowerCase().replace(/-\d+$/, "") ?? "";
  const roleKey = ROLE_DEFAULT_NAME[(role ?? "").toLowerCase()];
  // The generated PNG to try: the named pioneer's, else the role's primary.
  const imgKey = BY_NAME[key] ? key : roleKey;
  const [imgFailed, setImgFailed] = React.useState(false);

  if (imgKey && !imgFailed) {
    return (
      <img
        src={`/pioneers/${imgKey}.png`}
        alt={name ?? role ?? "pioneer"}
        className="w-full h-full object-cover"
        loading="lazy"
        draggable={false}
        onError={() => setImgFailed(true)}
      />
    );
  }
  // SVG fallback
  if (BY_NAME[key]) return BY_NAME[key];
  return BY_NAME[roleKey] ?? GENERIC;
}

/** Role → its primary pioneer, so role-only calls still get a face. */
const ROLE_DEFAULT_NAME: Record<string, string> = {
  researcher: "shannon",
  architect: "babbage",
  coder: "knuth",
  devops: "cerf",
  analyst: "codd",
  verifier: "hoare",
};

const SVG = "http://www.w3.org/2000/svg";

const BY_NAME: Record<string, React.ReactElement> = {
  // ── Researcher pool ──────────────────────────────────────────────────────
  shannon: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#33405c" />
      <path d="M31 72 L40 86 L49 72 L44 70 L40 73 L36 70 Z" fill="#eef1f5" />
      <path d="M33 75 L40 71 L33 67 Z M47 75 L40 71 L47 67 Z" fill="#7c2230" />
      <rect x="38.5" y="69.5" width="3" height="3.5" fill="#651b27" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="45" r="4" fill="#e8b78f" />
      <circle cx="57" cy="45" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="42" rx="17" ry="21" fill="#edc29c" />
      <path d="M23 38 C22 20 30 12 40 12 C50 12 58 20 57 38 C54 22 47 17 39 19 C33 21 26 27 23 38 Z" fill="#3a2c20" />
      <path d="M26 36 q5 -1.6 9 0" stroke="#3a2c20" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M45 36 q5 -1.6 9 0" stroke="#3a2c20" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="42" r="6.3" fill="none" stroke="#23262f" strokeWidth="2" />
      <circle cx="48" cy="42" r="6.3" fill="none" stroke="#23262f" strokeWidth="2" />
      <path d="M38.3 42 h3.4" stroke="#23262f" strokeWidth="2" />
      <path d="M25.7 42 L20 41" stroke="#23262f" strokeWidth="1.6" />
      <path d="M54.3 42 L60 41" stroke="#23262f" strokeWidth="1.6" />
      <circle cx="32" cy="42.3" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="42.3" r="1.6" fill="#2b2622" />
      <path d="M38.5 49 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 54 q5 2.5 10 0" stroke="#a9603f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
  minsky: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#4a4f59" />
      <path d="M33 72 L40 82 L47 72 L43 70 L40 72 L37 70 Z" fill="#dfe3ea" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="45" r="4" fill="#e8b78f" />
      <circle cx="57" cy="45" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="43" rx="17" ry="21" fill="#edc29c" />
      <path d="M22 41 C21 27 24 18 30 15 C26 21 24 30 24 41 Z" fill="#9b958b" />
      <path d="M58 41 C59 27 56 18 50 15 C54 21 56 30 56 41 Z" fill="#9b958b" />
      <path d="M30 15 Q40 12 50 15" stroke="#9b958b" strokeWidth="3" fill="none" strokeLinecap="round" opacity=".6" />
      <path d="M26 38 q5 -1.6 9 0" stroke="#7c776e" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M45 38 q5 -1.6 9 0" stroke="#7c776e" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <rect x="25.5" y="40" width="12" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="2" />
      <rect x="42.5" y="40" width="12" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="2" />
      <path d="M37.5 44.5 h5" stroke="#2b2622" strokeWidth="2" />
      <circle cx="31.5" cy="44.5" r="1.6" fill="#2b2622" />
      <circle cx="48.5" cy="44.5" r="1.6" fill="#2b2622" />
      <path d="M38.5 50 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 55 q5 -2 10 0" stroke="#a9603f" strokeWidth="1.4" fill="none" strokeLinecap="round" />
      <path d="M35 58 Q40 66 45 58 Q40 62 35 58 Z" fill="#9b958b" />
    </svg>
  ),
  johnson: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#6d2f44" />
      <path d="M30 72 Q40 78 50 72" stroke="#e9edf2" strokeWidth="2.5" fill="none" />
      <circle cx="34" cy="73" r="1.3" fill="#eef1f5" />
      <circle cx="40" cy="75" r="1.3" fill="#eef1f5" />
      <circle cx="46" cy="73" r="1.3" fill="#eef1f5" />
      <rect x="35" y="61" width="10" height="11" fill="#aa744a" />
      <circle cx="23" cy="45" r="4" fill="#b07a4d" />
      <circle cx="57" cy="45" r="4" fill="#b07a4d" />
      <ellipse cx="40" cy="43" rx="16.5" ry="20" fill="#bd8455" />
      <path d="M22 44 C20 27 30 14 40 14 C50 14 60 27 58 44 C57 34 51 25 40 25 C29 25 23 34 22 44 Z" fill="#1c1813" />
      <circle cx="26" cy="30" r="3.2" fill="#1c1813" />
      <circle cx="34" cy="24" r="3.2" fill="#1c1813" />
      <circle cx="46" cy="24" r="3.2" fill="#1c1813" />
      <circle cx="54" cy="30" r="3.2" fill="#1c1813" />
      <path d="M27 40 q4.5 -1.4 8 0" stroke="#1c1813" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M44.5 40 q4.5 -1.4 8 0" stroke="#1c1813" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <ellipse cx="32" cy="44" rx="5.6" ry="4.7" fill="none" stroke="#2b2622" strokeWidth="1.7" />
      <ellipse cx="48" cy="44" rx="5.6" ry="4.7" fill="none" stroke="#2b2622" strokeWidth="1.7" />
      <path d="M38.4 44 h3.2" stroke="#2b2622" strokeWidth="1.7" />
      <circle cx="32" cy="44" r="1.5" fill="#2b2622" />
      <circle cx="48" cy="44" r="1.5" fill="#2b2622" />
      <path d="M38.5 50 q1.5 1.3 3 0" stroke="#9c6334" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 55 q4 2 8 0" stroke="#7a3344" strokeWidth="1.8" fill="none" strokeLinecap="round" />
    </svg>
  ),
  // ── Architect pool ───────────────────────────────────────────────────────
  babbage: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 71 40 70 C59 71 74 79 74 96 Z" fill="#2a2a30" />
      <path d="M33 71 L40 84 L47 71 L40 73 Z" fill="#eef1f5" />
      <path d="M37 72 L40 80 L43 72 Z" fill="#3a3140" />
      <rect x="35" y="58" width="10" height="13" fill="#e0ad84" />
      <circle cx="23" cy="44" r="4" fill="#e8b78f" />
      <circle cx="57" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="40" rx="17" ry="21" fill="#edc29c" />
      <path d="M24 34 C24 16 31 11 40 11 C49 11 56 16 56 34 C52 18 46 15 40 15 C34 15 28 18 24 34 Z" fill="#8a857c" />
      <path d="M24 36 C22 49 25 57 31 60 C32 54 31 45 29 37 Z" fill="#8a857c" />
      <path d="M56 36 C58 49 55 57 49 60 C48 54 49 45 51 37 Z" fill="#8a857c" />
      <path d="M27 35 q5 -1.8 9 0" stroke="#6f6a61" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M44 35 q5 -1.8 9 0" stroke="#6f6a61" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="40" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="40" r="1.6" fill="#2b2622" />
      <path d="M38.5 47 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 53 q5 2.5 10 0" stroke="#a9603f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
  dijkstra: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#5b6b7a" />
      <path d="M33 72 L40 82 L47 72 L40 74 Z" fill="#cdd3da" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="24" cy="44" r="4" fill="#e8b78f" />
      <circle cx="56" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="42" rx="16" ry="22" fill="#edc29c" />
      <path d="M24 40 C22 18 30 12 40 11 C50 12 58 18 56 40 C54 22 48 18 40 18 C32 18 26 24 24 40 Z" fill="#6b6258" />
      <path d="M24 40 C23 48 24 54 27 57 C26 50 25 45 25 40 Z" fill="#6b6258" />
      <path d="M56 40 C57 48 56 54 53 57 C54 50 55 45 55 40 Z" fill="#6b6258" />
      <path d="M27 38 q5 -1.8 9 0" stroke="#534c43" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M44 38 q5 -1.8 9 0" stroke="#534c43" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="42" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="42" r="1.6" fill="#2b2622" />
      <path d="M38.5 49 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 55 q5 2 10 0" stroke="#a9603f" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  ),
  hamilton: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 80 21 73 40 72 C59 73 74 80 74 96 Z" fill="#6a8a86" />
      <path d="M34 73 L40 80 L46 73 L40 75 Z" fill="#e6ece8" />
      <rect x="35" y="61" width="10" height="12" fill="#e0ad84" />
      <path d="M24 36 C24 16 32 10 40 10 C48 10 56 16 56 36 L56 73 C54 61 52 50 50 42 C46 32 44 30 40 30 C36 30 34 32 30 42 C28 50 26 61 24 73 Z" fill="#3a2c20" />
      <ellipse cx="40" cy="40" rx="15" ry="20" fill="#edc29c" />
      <path d="M40 11 V25" stroke="#2a2018" strokeWidth="1.5" />
      <path d="M28 37 q4.5 -1.4 8 0" stroke="#3a2c20" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M43.5 37 q4.5 -1.4 8 0" stroke="#3a2c20" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <rect x="26" y="36" width="12" height="8.5" rx="3" fill="none" stroke="#2b2622" strokeWidth="1.8" />
      <rect x="42" y="36" width="12" height="8.5" rx="3" fill="none" stroke="#2b2622" strokeWidth="1.8" />
      <path d="M38 40 h4" stroke="#2b2622" strokeWidth="1.8" />
      <circle cx="32" cy="40.2" r="1.5" fill="#2b2622" />
      <circle cx="48" cy="40.2" r="1.5" fill="#2b2622" />
      <path d="M38.5 47 q1.5 1.3 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 53 q4 2 8 0" stroke="#b5604a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
  // ── Coder pool ─────────────────────────────────────────────────────────────
  knuth: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#6a5b4a" />
      <path d="M34 72 L40 80 L46 72 L40 74 Z" fill="#cfc6b8" />
      <rect x="35" y="59" width="10" height="11" fill="#e0ad84" />
      <circle cx="23" cy="43" r="4" fill="#e8b78f" />
      <circle cx="57" cy="43" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="40" rx="17" ry="21" fill="#edc29c" />
      <path d="M22 38 C21 26 24 19 30 16 C26 21 24 29 24 38 Z" fill="#b3aea4" />
      <path d="M58 38 C59 26 56 19 50 16 C54 21 56 29 56 38 Z" fill="#b3aea4" />
      <path d="M31 16 Q40 13 49 16" stroke="#b3aea4" strokeWidth="3" fill="none" strokeLinecap="round" opacity=".55" />
      <path d="M26 36 q5 -1.6 9 0" stroke="#9a948a" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M45 36 q5 -1.6 9 0" stroke="#9a948a" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="41" r="6.2" fill="none" stroke="#23262f" strokeWidth="2" />
      <circle cx="48" cy="41" r="6.2" fill="none" stroke="#23262f" strokeWidth="2" />
      <path d="M38.5 41 h3" stroke="#23262f" strokeWidth="2" />
      <circle cx="32" cy="41" r="1.5" fill="#2b2622" />
      <circle cx="48" cy="41" r="1.5" fill="#2b2622" />
      <path d="M27 49 C25 62 33 73 40 74 C47 73 55 62 53 49 C46 56 44 57 40 57 C36 57 34 56 27 49 Z" fill="#d8d4cc" />
      <path d="M32 50 Q40 54 48 50 Q40 47 32 50 Z" fill="#d8d4cc" />
    </svg>
  ),
  lovelace: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 22 73 40 72 C58 73 74 79 74 96 Z" fill="#2f3a63" />
      <path d="M31 73 Q40 79 49 73 L46 67 Q40 70 34 67 Z" fill="#dfe3ea" />
      <rect x="36" y="61" width="8" height="11" fill="#e3b591" />
      <ellipse cx="40" cy="43" rx="16" ry="20" fill="#edc29c" />
      <path d="M24 43 C23 25 31 17 40 17 C49 17 57 25 56 43 C52 29 47 26 40 26 C33 26 28 29 24 43 Z" fill="#2e2218" />
      <path d="M40 17 V27" stroke="#1f180f" strokeWidth="1.5" />
      <circle cx="22" cy="47" r="5" fill="#2e2218" />
      <circle cx="21" cy="55" r="4" fill="#2e2218" />
      <circle cx="58" cy="47" r="5" fill="#2e2218" />
      <circle cx="59" cy="55" r="4" fill="#2e2218" />
      <path d="M29 41 q4 -1.3 7.5 0" stroke="#2e2218" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M43.5 41 q4 -1.3 7.5 0" stroke="#2e2218" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <circle cx="33" cy="44" r="1.5" fill="#2b2622" />
      <circle cx="47" cy="44" r="1.5" fill="#2b2622" />
      <path d="M38.5 50 q1.5 1.3 3 0" stroke="#dca87f" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 55 q4 2 8 0" stroke="#9c3f57" strokeWidth="1.7" fill="none" strokeLinecap="round" />
    </svg>
  ),
  ritchie: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#4f5b52" />
      <path d="M34 72 L40 79 L46 72 L40 74 Z" fill="#cdd1c8" />
      <rect x="35" y="58" width="10" height="11" fill="#e0ad84" />
      <circle cx="23" cy="43" r="4" fill="#e8b78f" />
      <circle cx="57" cy="43" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="38" rx="17" ry="21" fill="#edc29c" />
      <path d="M23 35 C22 16 31 10 40 9 C49 10 58 16 57 35 C52 18 47 14 40 14 C33 14 28 18 23 35 Z" fill="#5a4632" />
      <path d="M26 36 q5 -1.6 9 0" stroke="#3f3122" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M45 36 q5 -1.6 9 0" stroke="#3f3122" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="40" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="40" r="1.6" fill="#2b2622" />
      <path d="M38.6 45 q1.4 1.2 2.8 0" stroke="#3f3122" strokeWidth="1.2" fill="none" strokeLinecap="round" />
      <path d="M27 47 C25 61 33 72 40 74 C47 72 55 61 53 47 C46 55 44 57 40 57 C36 57 34 55 27 47 Z" fill="#5a4632" />
      <path d="M32 49 Q40 53 48 49 Q40 46 32 49 Z" fill="#5a4632" />
    </svg>
  ),
  // ── DevOps pool ────────────────────────────────────────────────────────────
  cerf: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#2c3340" />
      <path d="M33 72 L40 84 L47 72 L40 74 Z" fill="#eef1f5" />
      <path d="M37 72 L40 86 L43 72 Z" fill="#6a2230" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="44" r="4" fill="#e8b78f" />
      <circle cx="57" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="41" rx="17" ry="20" fill="#edc29c" />
      <path d="M24 36 C24 18 31 13 40 13 C49 13 56 18 56 36 C52 20 46 17 40 17 C34 17 28 20 24 36 Z" fill="#b3aea4" />
      <path d="M27 38 q5 -1.6 9 0" stroke="#9a948a" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M44 38 q5 -1.6 9 0" stroke="#9a948a" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <rect x="26" y="40" width="11" height="8" rx="2" fill="none" stroke="#3a3a40" strokeWidth="1.5" />
      <rect x="43" y="40" width="11" height="8" rx="2" fill="none" stroke="#3a3a40" strokeWidth="1.5" />
      <path d="M37 44 h6" stroke="#3a3a40" strokeWidth="1.5" />
      <circle cx="31.5" cy="44" r="1.4" fill="#2b2622" />
      <circle cx="48.5" cy="44" r="1.4" fill="#2b2622" />
      <path d="M25 44 C23 60 32 74 40 76 C48 74 57 60 55 44 C47 53 44 55 40 55 C36 55 33 53 25 44 Z" fill="#cbc7bf" />
      <path d="M31 47 Q40 52 49 47 Q40 44 31 47 Z" fill="#cbc7bf" />
    </svg>
  ),
  torvalds: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#3f5a4d" />
      <path d="M32 72 Q40 77 48 72 L48 75 L32 75 Z" fill="#33493e" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="44" r="4" fill="#e8b78f" />
      <circle cx="57" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="42" rx="18" ry="21" fill="#edc29c" />
      <path d="M22 38 C21 22 30 15 40 15 C50 15 59 22 58 38 C55 28 49 24 40 24 C31 24 25 28 22 38 Z" fill="#5a4a3a" />
      <path d="M26 39 q5 -1.6 9 0" stroke="#43372a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M45 39 q5 -1.6 9 0" stroke="#43372a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <ellipse cx="32" cy="43" rx="6" ry="5" fill="none" stroke="#23262f" strokeWidth="2" />
      <ellipse cx="48" cy="43" rx="6" ry="5" fill="none" stroke="#23262f" strokeWidth="2" />
      <path d="M38 43 h4" stroke="#23262f" strokeWidth="2" />
      <circle cx="32" cy="43" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="43" r="1.6" fill="#2b2622" />
      <path d="M38.5 50 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 55 q5 2.5 10 0" stroke="#a9603f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
  perlman: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 80 21 73 40 72 C59 73 74 80 74 96 Z" fill="#5f7a8a" />
      <path d="M34 73 L40 79 L46 73 L40 75 Z" fill="#e2e7ea" />
      <rect x="35" y="61" width="10" height="12" fill="#e0ad84" />
      <path d="M24 37 C24 17 32 11 40 11 C48 11 56 17 56 37 L55 66 C53 56 52 48 51 42 C47 32 44 30 40 30 C36 30 33 32 29 42 C28 48 27 56 25 66 Z" fill="#4a3a2a" />
      <ellipse cx="40" cy="41" rx="15" ry="20" fill="#edc29c" />
      <path d="M44 14 C42 20 40 28 38 37" stroke="#34281c" strokeWidth="1.4" fill="none" />
      <path d="M28 40 q4 -1.4 7.5 0" stroke="#34281c" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M44.5 40 q4 -1.4 7.5 0" stroke="#34281c" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <circle cx="33" cy="43" r="5.6" fill="none" stroke="#2b2622" strokeWidth="1.8" />
      <circle cx="47" cy="43" r="5.6" fill="none" stroke="#2b2622" strokeWidth="1.8" />
      <path d="M38.6 43 h2.8" stroke="#2b2622" strokeWidth="1.8" />
      <circle cx="33" cy="43" r="1.5" fill="#2b2622" />
      <circle cx="47" cy="43" r="1.5" fill="#2b2622" />
      <path d="M38.5 49 q1.5 1.3 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 54 q4 2 8 0" stroke="#b5604a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
  // ── Analyst pool ───────────────────────────────────────────────────────────
  codd: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#5f6772" />
      <path d="M33 72 L40 84 L47 72 L40 74 Z" fill="#eef1f5" />
      <path d="M37 72 L40 86 L43 72 Z" fill="#27324a" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="44" r="4" fill="#e8b78f" />
      <circle cx="57" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="41" rx="17" ry="20" fill="#edc29c" />
      <path d="M23 37 C22 19 31 13 40 12 C49 13 58 19 57 37 C52 21 45 17 38 19 C32 21 26 28 23 37 Z" fill="#8f8a80" />
      <path d="M27 38 q5 -1.6 9 0" stroke="#746f66" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M44 38 q5 -1.6 9 0" stroke="#746f66" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <rect x="25.5" y="40" width="12.5" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="1.9" />
      <rect x="42" y="40" width="12.5" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="1.9" />
      <path d="M38 44.5 h4" stroke="#2b2622" strokeWidth="1.9" />
      <circle cx="31.7" cy="44.5" r="1.5" fill="#2b2622" />
      <circle cx="48.3" cy="44.5" r="1.5" fill="#2b2622" />
      <path d="M38.5 50 q1.5 1.3 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 55 q4 2 8 0" stroke="#a9603f" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  ),
  hopper: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#1f2a44" />
      <path d="M31 72 L40 84 L40 73 Z" fill="#16203a" />
      <path d="M49 72 L40 84 L40 73 Z" fill="#28365a" />
      <rect x="14" y="85" width="12" height="2.4" fill="#d9b34a" />
      <rect x="14" y="89" width="12" height="2.4" fill="#d9b34a" />
      <rect x="35" y="58" width="10" height="11" fill="#e0ad84" />
      <circle cx="24" cy="44" r="3.6" fill="#e8b78f" />
      <circle cx="56" cy="44" r="3.6" fill="#e8b78f" />
      <ellipse cx="40" cy="42" rx="16" ry="19" fill="#e8bd95" />
      <path d="M30 41 q4 -1.4 7.5 0" stroke="#2e2620" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M42.5 41 q4 -1.4 7.5 0" stroke="#2e2620" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <circle cx="34" cy="43" r="1.5" fill="#2b2622" />
      <circle cx="46" cy="43" r="1.5" fill="#2b2622" />
      <path d="M38.5 48 q1.5 1.3 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 53 q4 2 8 0" stroke="#a9603f" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M22 28 Q40 16 58 28 L58 31 Q40 24 22 31 Z" fill="#1f2a44" />
      <rect x="22" y="30" width="36" height="5" fill="#eef1f5" />
      <circle cx="40" cy="27" r="2.6" fill="#d9b34a" />
      <path d="M19 35 Q40 42 61 35 L59 39 Q40 45 21 39 Z" fill="#14181f" />
    </svg>
  ),
  boole: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 71 40 70 C59 71 74 79 74 96 Z" fill="#2a2a32" />
      <path d="M33 71 L40 82 L47 71 L40 73 Z" fill="#eef1f5" />
      <path d="M37 72 L40 78 L43 72 Z" fill="#3a3140" />
      <rect x="35" y="58" width="10" height="13" fill="#e0ad84" />
      <ellipse cx="40" cy="40" rx="17" ry="21" fill="#edc29c" />
      <path d="M24 35 C24 17 31 12 40 11 C49 12 56 17 56 35 C52 19 46 15 40 15 C34 15 28 19 24 35 Z" fill="#3a2c20" />
      <path d="M24 37 C22 50 25 58 32 61 C33 54 31 45 29 38 Z" fill="#3a2c20" />
      <path d="M56 37 C58 50 55 58 48 61 C47 54 49 45 51 38 Z" fill="#3a2c20" />
      <path d="M27 35 q5 -1.8 9 0" stroke="#2a2018" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M44 35 q5 -1.8 9 0" stroke="#2a2018" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="40" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="40" r="1.6" fill="#2b2622" />
      <path d="M38.5 47 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 53 q5 2 10 0" stroke="#a9603f" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  ),
  // ── Verifier pool ──────────────────────────────────────────────────────────
  hoare: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#3a4452" />
      <path d="M33 72 L40 82 L47 72 L40 74 Z" fill="#dfe3ea" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="44" r="4" fill="#e8b78f" />
      <circle cx="57" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="41" rx="17" ry="20" fill="#edc29c" />
      <path d="M23 37 C22 19 31 13 40 12 C49 13 58 19 57 37 C52 21 46 17 40 17 C34 17 28 21 23 37 Z" fill="#cdc8c0" />
      <path d="M27 38 q5 -1.6 9 0" stroke="#b3aea4" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M44 38 q5 -1.6 9 0" stroke="#b3aea4" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <rect x="25.5" y="40" width="12.5" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="1.9" />
      <rect x="42" y="40" width="12.5" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="1.9" />
      <path d="M38 44.5 h4" stroke="#2b2622" strokeWidth="1.9" />
      <circle cx="31.7" cy="44.5" r="1.5" fill="#2b2622" />
      <circle cx="48.3" cy="44.5" r="1.5" fill="#2b2622" />
      <path d="M38.5 50 q1.5 1.3 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 55 q4 2 8 0" stroke="#a9603f" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  ),
  turing: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#5a5240" />
      <path d="M32 72 L40 80 L48 72 L44 70 L40 74 L36 70 Z" fill="#eef1f5" />
      <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="44" r="4" fill="#e8b78f" />
      <circle cx="57" cy="44" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="41" rx="17" ry="21" fill="#edc29c" />
      <path d="M24 36 C23 18 31 12 40 11 C49 12 57 18 56 36 C52 20 47 16 40 18 C35 19 28 23 24 36 Z" fill="#4a3a2a" />
      <path d="M27 38 q5 -1.6 9 0" stroke="#34281c" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M44 38 q5 -1.6 9 0" stroke="#34281c" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="32" cy="42" r="1.6" fill="#2b2622" />
      <circle cx="48" cy="42" r="1.6" fill="#2b2622" />
      <path d="M38.5 49 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M35 55 q5 2.5 10 0" stroke="#a9603f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
  liskov: (
    <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
      <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
      <path d="M6 96 C6 80 21 73 40 72 C59 73 74 80 74 96 Z" fill="#4a5a6a" />
      <path d="M33 73 L40 80 L47 73 L40 75 Z" fill="#e2e7ea" />
      <rect x="35" y="61" width="10" height="12" fill="#e0ad84" />
      <circle cx="23" cy="45" r="4" fill="#e8b78f" />
      <circle cx="57" cy="45" r="4" fill="#e8b78f" />
      <ellipse cx="40" cy="43" rx="16.5" ry="20" fill="#edc29c" />
      <path d="M23 42 C22 24 31 15 40 15 C49 15 58 24 57 42 C54 31 48 25 40 25 C32 25 26 31 23 42 Z" fill="#8a7d6e" />
      <path d="M23 42 C23 49 25 54 28 56 C27 50 26 45 26 42 Z" fill="#8a7d6e" />
      <path d="M57 42 C57 49 55 54 52 56 C53 50 54 45 54 42 Z" fill="#8a7d6e" />
      <path d="M28 41 q4.5 -1.5 8 0" stroke="#6f6456" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <path d="M43.5 41 q4.5 -1.5 8 0" stroke="#6f6456" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      <rect x="26" y="42" width="12" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="1.8" />
      <rect x="42" y="42" width="12" height="9" rx="2" fill="none" stroke="#2b2622" strokeWidth="1.8" />
      <path d="M38 46.5 h4" stroke="#2b2622" strokeWidth="1.8" />
      <circle cx="32" cy="46.5" r="1.5" fill="#2b2622" />
      <circle cx="48" cy="46.5" r="1.5" fill="#2b2622" />
      <path d="M38.5 52 q1.5 1.3 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
      <path d="M36 57 q4 2 8 0" stroke="#b5604a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  ),
};

/** Neutral fallback bust for any unmatched pioneer. */
const GENERIC: React.ReactElement = (
  <svg viewBox="0 0 80 96" className="w-full h-full" xmlns={SVG}>
    <rect x="0" y="0" width="80" height="96" fill="#e9edf2" />
    <path d="M6 96 C6 79 21 72 40 71 C59 72 74 79 74 96 Z" fill="#5a606b" />
    <rect x="35" y="60" width="10" height="12" fill="#e0ad84" />
    <circle cx="23" cy="44" r="4" fill="#e8b78f" />
    <circle cx="57" cy="44" r="4" fill="#e8b78f" />
    <ellipse cx="40" cy="41" rx="17" ry="21" fill="#edc29c" />
    <path d="M23 38 C22 20 31 13 40 12 C49 13 58 20 57 38 C52 22 46 18 40 18 C34 18 28 22 23 38 Z" fill="#5b5048" />
    <circle cx="32" cy="41" r="1.6" fill="#2b2622" />
    <circle cx="48" cy="41" r="1.6" fill="#2b2622" />
    <path d="M38.5 48 q1.5 1.4 3 0" stroke="#d89f73" strokeWidth="1.3" fill="none" strokeLinecap="round" />
    <path d="M35 54 q5 2.5 10 0" stroke="#a9603f" strokeWidth="1.6" fill="none" strokeLinecap="round" />
  </svg>
);
