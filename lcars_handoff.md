# Handoff Spec — LCARS / Okudagram Theme for Memex

> **Target:** the Memex chat shell — left rail, top header, center void, right rail, bottom strip.
> **Renderer:** React + Canvas (assumed `react-konva`; primitives translate to plain Canvas2D or PixiJS without change).
> **Philosophy reference:** `lcars_philosophy.md`. **Visual reference:** `lcars_reference.png`.

The screen is **anatomy, not chrome.** Every visible element is a load-bearing piece of an information system. There is no skeuomorphism, no glow, no gradient, no scroll-jacked parallax. The interface communicates by **shape, color, and absence**. Stillness is the interface — motion is reserved for actual data changes, never for decoration.

---

## 1. Overview

A working LCARS terminal — quiet competence, master-elbow architecture, flat saturated color blocks, monospaced ID anchors. The user should feel they have sat down at a Bridge Operations console on the third hour of a routine shift: nothing screams, nothing flashes, nothing moves except real data updates.

The implementation replaces the current Memex shell wholesale. It does not skin existing widgets; it re-renders the entire frame as a single canvas composition driven by a layout schema.

---

## 2. Design Tokens

### 2.1 Color taxonomy

Color in LCARS is **not decoration — it is a sub-system tag**. Each hue owns a domain the operator learns by use. Use these tokens; do not freelance.

| Token             | Hex       | Owns                                                      |
| ----------------- | --------- | --------------------------------------------------------- |
| `--lc-bg`         | `#000000` | Pure black canvas. No `#0a0a0a`. No navy. Pure black.     |
| `--lc-amber`      | `#FF9966` | Primary brand / monumental headline / primary elbow       |
| `--lc-peach`      | `#FFCC99` | Secondary header segments / informational                 |
| `--lc-gold`       | `#FFCC63` | Numeric / status tags                                     |
| `--lc-salmon`     | `#CC6666` | Bottom elbow / alert-adjacent                             |
| `--lc-brick`      | `#CC6633` | Heavy structural accent                                   |
| `--lc-lilac`      | `#CC99CC` | Operations data / sub-header strip                        |
| `--lc-periwinkle` | `#9999FF` | Navigational                                              |
| `--lc-cream`      | `#FFE0C0` | Body readout values (warm white, not pure white)          |
| `--lc-grey`       | `#968474` | Secondary labels / keys in key/value pairs                |
| `--lc-dim`        | `#604C3E` | Ticker text, registration marks, "trust anchor" data      |

Disallowed: pure white, neon green, blue accents, drop shadows, gradients of any kind. The void is `--lc-bg`. Always.

### 2.2 Typography

Authentic LCARS used Microgramma / Eurostile Bold Extended. We use:

| Token             | Family            | Use                                                 |
| ----------------- | ----------------- | --------------------------------------------------- |
| `--lc-font-mono-headline`   | **Big Shoulders Display Bold** | Monumental wordmarks (`MEMEX`, `OPERATIONAL`)        |
| `--lc-font-tag`             | **Big Shoulders Display Bold** | Header / footer arm tags (~`58px`)                   |
| `--lc-font-ui`              | **Jura Medium**                | All caps labels inside color blocks                  |
| `--lc-font-ui-light`        | **Jura Light**                 | Micro registration marks                             |
| `--lc-font-data`            | **DM Mono Regular**            | Numeric IDs, stardates, key/value values             |

**Rules:**

- All UI labels (anything inside a color block) are `ALL CAPS`, `letter-spacing: 0.04em`.
- Body chat content is the **only** non-caps text in the entire shell. Set in Jura Medium, sentence case.
- Headlines (`MEMEX`, `OPERATIONAL`) are very large — never use mid-size display text. The hierarchy is *monumental → whispered*, with nothing in between.
- Numeric anchors (`47023.4`, `NCC-MX-47-0801`) use `--lc-font-data` regardless of context.

### 2.3 Spacing

8-pt baseline grid. Tokens (in px at 1× DPR):

| Token         | Value | Use                                              |
| ------------- | ----- | ------------------------------------------------ |
| `--lc-s-1`    | 4     | Inside-tag padding                               |
| `--lc-s-2`    | 8     | Between color bands (the canonical LCARS gap)    |
| `--lc-s-3`    | 16    | Between strip rows                               |
| `--lc-s-4`    | 24    | Between major regions                            |
| `--lc-s-5`    | 40    | Between elbow body and inset content             |
| `--lc-s-6`    | 60    | Outer canvas margin (the void's outer breathing) |

### 2.4 Radii & weights

| Token              | Value      | Use                                                              |
| ------------------ | ---------- | ---------------------------------------------------------------- |
| `--lc-radius-arm`  | `t_v` size | Elbow outer corner = max(armV, armH). The shape's defining ratio |
| `--lc-radius-stadium` | `h / 2` | All stadium / cap-left / cap-right shapes                        |
| `--lc-header-h`    | `130`      | Top elbow horizontal arm height                                  |
| `--lc-footer-h`    | `110`      | Bottom elbow horizontal arm height (slightly shorter, on purpose)|
| `--lc-spine-w`     | `220`      | Left vertical arm width                                          |
| `--lc-rspine-w`    | `90`       | Right secondary spine width                                      |
| `--lc-strip-h`     | `32`       | Sub-header / sub-footer thin strip                               |
| `--lc-divider-w`   | `3`        | Static rule under headline                                       |

---

## 3. Primitive Components

The entire shell is composed from **four** canvas primitives. Implement them as `react-konva` `Group` components; the rest of the UI calls them.

### 3.1 `<Elbow />` — the keystone

Two bars joined at one rounded outer corner. Inner corner is a clean right angle. This is the LCARS shape. Everything else is downstream of this.

```tsx
type Corner = 'NW' | 'NE' | 'SW' | 'SE';

interface ElbowProps {
  x: number; y: number;            // top-left of bounding box
  w: number; h: number;            // full extent of the L
  armH: number;                    // horizontal arm thickness
  armV: number;                    // vertical arm thickness
  color: string;
  corner: Corner;                  // which outer corner is rounded
}
```

**Geometry (NW corner):**

```
r = max(armH, armV)

draw filled rect:     (x+r, y)              → (x+w,   y+armH)        // horizontal arm
draw filled rect:     (x,   y+r)            → (x+armV, y+h)          // vertical arm
draw filled arc:      center (x+r, y+r), radius r, 180° → 270°       // outer rounded corner
draw filled BLACK:    (x+armV, y+armH)      → (x+r,    y+r)          // sharpen the inner corner
```

Other corners are 90° rotations. **Do not** anti-alias the inner corner — leave it crisp.

Used only twice per screen: master NW elbow at top, master SW elbow at bottom. Resist the urge to spawn more.

### 3.2 `<Stadium />` — button form

Rectangle with semicircular ends. Used **only** for actionable controls (Memory, Research, Swarm, Go, Send).

```tsx
interface StadiumProps {
  x: number; y: number; w: number; h: number;
  color: string;
  label?: string;
  state?: 'default' | 'hover' | 'active' | 'disabled';
  onClick?: () => void;
}
```

Width must be ≥ `2h` (anything shorter is a circle, not a stadium). Label is centered, `--lc-font-ui` `26px`, BLACK fill on color.

### 3.3 `<CapLeft />` / `<CapRight />` — header segments

A bar with **one** rounded end. Used for sub-header strips, footer strips, and the segments to the right of the master elbows.

```tsx
interface CapProps {
  x: number; y: number; w: number; h: number; color: string;
  children?: TextNode;
}
```

Cap-right has its right end rounded (head end "pointing" left). Cap-left has its left end rounded. They are not buttons — they are panel headers. Do not bind `onClick` to them.

### 3.4 `<Band />` — segmented spine block

A flat rectangle with a small caps label and a numeric tag. Used inside the left spine and right spine. Variable height per band, fixed 8-px black gap between bands.

```tsx
interface BandProps {
  x: number; y: number; w: number; h: number;
  color: string;
  label: string;       // "OPS", "HELM", "TAC", …
  code: string;        // "12-04"  (numeric trust-anchor)
}
```

Label is **right-aligned** in the left spine (so it reads against the spine), **center-aligned** in the right spine (so it reads against open void on both sides).

---

## 4. Layout architecture

Conceive the shell as a **6-zone schema** computed at every resize. Do not center anything — LCARS is deliberately asymmetric.

```
┌─────────────────────────────────────────────────────────────────┐
│  ●  HEADER ELBOW (NW, amber)  ─────────  cap_R  ───  cap_L      │
│  ●                                                              │
│  ●  ┌──────────────────────────────────────────────────┐        │
│  ●  │  sub-header strip   ────────────  numeric cap    │        │
│  S  │                                                  │  R-    │
│  P  │                                                  │  S     │
│  I  │       ███████ MONUMENTAL WORDMARK ███████        │  P     │
│  N  │       ─────────────────────────────              │  I     │
│  E  │                                                  │  N     │
│  ●  │   ┌────────┐  ┌────────┐  ┌────────┐             │  E     │
│  ●  │   │PROPULS │  │OPS     │  │LIFE SUP│             │        │
│  ●  │   │……      │  │……      │  │……      │             │        │
│  ●  │   └────────┘  └────────┘  └────────┘             │        │
│  ●  │                                                  │        │
│  ●  │   MANIFEST ─────────────────────────────────     │        │
│  ●  │   47024.1   SUBSPACE CARRIER        LOCKED       │        │
│  ●  │   47024.0   SHUTTLE BAY 2           SEALED       │        │
│  ●  │                                                  │        │
│  ●  │   (MEMORY) (RESEARCH) (SWARM) (GO)               │        │
│  ●  │                                                  │        │
│  ●  │   sub-footer strip   ─────────  ALPHA / NCC-…    │        │
│  ●  └──────────────────────────────────────────────────┘        │
│  ●  FOOTER ELBOW (SW, salmon) ─────────  cap_L  ───  cap_R      │
└─────────────────────────────────────────────────────────────────┘
```

| Zone | Token reference                          | Notes                                          |
| ---- | ---------------------------------------- | ---------------------------------------------- |
| 1    | Top header elbow + cap segments          | One NW elbow + 1–2 caps, gap of `--lc-s-4`     |
| 2    | Sub-header strip                         | `--lc-strip-h`, lilac + gold caps              |
| 3    | Left spine bands                         | 7–9 bands; heights computed by weights, not equal |
| 4    | Central void (chat / readouts / manifest)| Black, generous padding `--lc-s-5`             |
| 5    | Right secondary spine                    | Slimmer (`--lc-rspine-w`), fewer bands         |
| 6    | Sub-footer strip + footer elbow          | Mirror of zones 1–2 but salmon-led             |

---

## 5. Component Mapping (Existing Memex → LCARS)

| Existing Memex element                          | LCARS replacement                                                            |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| Left-rail menu (`CHAT`, `MEDIA`, `PALACE` …)    | `<Band>` per item, color-coded by domain, height 90–140 px                   |
| Top bar (`HOLOGRAPHIC BRIDGE`, `NCC-1701`)      | Sub-header strip (`<CapLeft>` + `<CapRight>`) inside the elbow's right arm   |
| Right stat bars (`COMM`, `NAV`, `SCI` …)        | Right secondary spine (`<Band>` stack) + a small data-readout column         |
| Sensor radar circle                             | Static circle: 3 concentric strokes `--lc-amber`, no rotation; one dim tick  |
| Center chat / planner panes                     | Black void; chat bubbles are flat rectangles with no rounded corners except a single `<CapLeft>` accent strip per turn |
| Bottom info strip                               | Sub-footer strip + bottom elbow (`<Elbow corner="SW" color="--lc-salmon">`)  |
| `+ NEW CHAT`                                    | `<Stadium color="--lc-amber" label="+ NEW CHAT" />`                          |
| Send button (`GO`)                              | `<Stadium color="--lc-amber" label="GO" />`                                  |
| Style config / audio / reset buttons            | Small stadiums, periwinkle, grouped at the bottom of the right spine         |

---

## 6. States & Interactions

LCARS is a calm system. Hover/active states are subtle color shifts, not animations.

| Element            | State       | Behavior                                                                                |
| ------------------ | ----------- | --------------------------------------------------------------------------------------- |
| `<Band>`           | hover       | Fill shifts +6 % luminance. Cursor `pointer`. **No scale, no glow.**                    |
| `<Band>`           | active/selected | Inverts: label color becomes BLACK on fill (no change if already BLACK), and a 3-px BLACK chord notch appears on the inner edge (LCARS "selected" indicator). |
| `<Stadium>`        | hover       | Fill +8 % luminance.                                                                    |
| `<Stadium>`        | active      | Fill briefly inverts to BLACK with label in original color for `60 ms`, then restores.  |
| `<Stadium>`        | disabled    | Fill desaturates to `#5a4a3e`, label `--lc-grey`.                                       |
| `<CapLeft/Right>`  | (n/a)       | Decorative, not interactive.                                                            |
| Manifest row       | hover       | Row underline appears in `--lc-dim`. Click → details.                                   |
| Chat input         | focus       | A 2-px `--lc-amber` cap-right strip slides under the input field. No glow.              |

**Cursor:** default `default`; over Bands/Stadiums `pointer`. Never `text` unless inside an input.

---

## 7. Motion

Motion is **only** for actual data updates. Catalog:

| Where                       | Trigger                  | Animation                                                                  | Duration | Easing             |
| --------------------------- | ------------------------ | -------------------------------------------------------------------------- | -------- | ------------------ |
| Stardate ticker (right edge)| New tick every `2.4 s`   | Last value fades to `--lc-dim`, new value appears at top with full opacity | `120 ms` | `linear`           |
| Readout numeric value       | Underlying datum changes | Old value crossfades to new                                                | `180 ms` | `ease-out-quad`    |
| `<Stadium>` active flash    | onClick                  | Color invert hold then restore                                             | `60 ms`  | step (no easing)   |
| Radar tick (optional)       | Idle                     | One tick mark traverses the 3-ring radar, 1 revolution per `6.0 s`         | linear   | constant           |
| New chat turn appears       | Message arrives          | Row slides up `8 px` while fading in                                       | `220 ms` | `ease-out`         |

**Disallowed motion:** sweeping gradients, glowing pulses, parallax scrolling, button hover scale, "energy" trails, particle effects, screen wipes, anything bouncy, anything that draws the eye away from data.

---

## 8. Layout Schema (data-driven)

Drive the layout from a single JSON schema; the canvas renders it. This is critical for maintainability and lets you re-theme by swapping the schema.

```ts
type Hue = 'amber' | 'peach' | 'gold' | 'salmon' | 'brick' | 'lilac' | 'periwinkle';

interface Schema {
  header: {
    elbow: { color: Hue; armH: number; armV: number; body: { w: number; h: number } };
    caps: Array<{ kind: 'capRight' | 'capLeft'; color: Hue; w: number; lines: string[] }>;
    subStrip: Array<{ kind: 'capLeft' | 'capRight'; color: Hue; w: number; text: string }>;
  };
  spineLeft: Array<{ label: string; code: string; color: Hue; weight: number; route?: string }>;
  spineRight: Array<{ label: string; color: Hue; weight: number }>;
  footer: { /* mirror of header */ };
  void: { /* chat / readouts; addressed by their own components */ };
}
```

Weights normalize to fill available vertical space — never set absolute heights for spine bands. This guarantees the spine fills exactly between the two elbow vertical arms with no remainder.

---

## 9. Responsive Behavior

Canvas renders to **CSS pixels at devicePixelRatio**; recompute the schema on resize.

| Breakpoint           | Behavior                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| Desktop (≥ 1280 px)  | Full 6-zone schema. Spine `220 px`, RSpine `90 px`, void breathes.                                |
| Compact (1024–1279)  | Spine narrows to `180 px`. RSpine collapses to a status column (no labels).                       |
| Tablet (768–1023)    | Footer elbow vertical arm hides; bottom becomes a flat strip. Right spine disappears entirely.    |
| Mobile (< 768)       | Single column. Header collapses to a 60 px capLeft+capRight strip; left spine becomes a drawer triggered by a stadium button. |

Re-render the canvas at the new layout on resize — do **not** scale a fixed-size canvas. Bands lose meaning if pixel-scaled.

---

## 10. Edge Cases

- **Empty chat:** Show the monumental wordmark only. Below it, the line `AWAITING DIRECTIVE  ·  STARDATE  47023.4` in `--lc-amber`, Jura Medium 38 px. Do not show illustrations.
- **Long subsystem label** (e.g., `LIFE SUPPORT`): Tighten letter-spacing to `0` once over 8 chars; never wrap inside a band — re-design the band to be wider.
- **Loading**: A `<Band>` becomes `--lc-dim` with a static `· · ·` label. No spinner. Stillness even when waiting.
- **Error**: A `<CapLeft color="--lc-salmon" />` appears at the top of the void with the error text in BLACK. No icon, no red flash.
- **Offline connector**: That subsystem's `<Band>` mutes to `--lc-dim`, label `OFFLINE`. No exclamation marks.
- **Locale (long strings)**: Headlines never localize — `MEMEX` is the wordmark. Labels truncate with no ellipsis (the LCARS convention) — if it doesn't fit, the band is wrong.

---

## 11. Accessibility

LCARS aesthetic must not break a screen reader.

- All canvas-rendered text must have a parallel DOM `<div role="presentation" aria-hidden="false">` mirror, positioned offscreen, so AT can read it. (`react-konva` doesn't expose text to AT — supplement with hidden DOM.)
- `<Band>` and `<Stadium>` are interactive; expose them as `<button>` elements absolutely positioned over their canvas hitboxes, with the visible canvas decoration purely cosmetic. Bind keyboard handlers (`Enter`, `Space`) to the DOM buttons.
- **Focus indicator:** a 2 px `--lc-amber` outline drawn just outside the band/stadium when the corresponding DOM button is focused.
- **Color contrast:** every label color/background pair in the palette is ≥ 7:1 (BLACK on AMBER = 11.6:1; verify per pair).
- **Color-only meaning:** subsystem hue is **paired** with its caps text — no info is conveyed by color alone.
- **Motion-prefers-reduced-motion:** disable the stardate ticker fade and the radar tick. Numeric crossfades become instant swaps.

---

## 12. Implementation Notes (React + Canvas)

### 12.1 Recommended library

`react-konva` is the right choice: declarative, supports `Group`, supports custom `Shape` for the elbow primitive, integrates cleanly with React state. PixiJS is overkill (no animation density). Plain Canvas2D works but you lose the JSX scene graph.

### 12.2 Custom shape — the elbow

```tsx
import { Shape } from 'react-konva';

export const Elbow: React.FC<ElbowProps> = ({
  x, y, w, h, armH, armV, color, corner,
}) => (
  <Shape
    sceneFunc={(ctx, shape) => {
      const r = Math.max(armH, armV);
      ctx.beginPath();
      if (corner === 'NW') {
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w, y);
        ctx.lineTo(x + w, y + armH);
        ctx.lineTo(x + r, y + armH);
        ctx.lineTo(x + r, y + r);          // inner crisp corner
        ctx.lineTo(x + armV, y + r);
        ctx.lineTo(x + armV, y + h);
        ctx.lineTo(x, y + h);
        ctx.lineTo(x, y + r);
        ctx.arc(x + r, y + r, r, Math.PI, 1.5 * Math.PI);
      }
      // ...analogous for SW/NE/SE
      ctx.closePath();
      ctx.fillStrokeShape(shape);
    }}
    fill={color}
    listening={false}    // master elbows are decorative
    perfectDrawEnabled={false}
  />
);
```

### 12.3 Performance

- Set `perfectDrawEnabled={false}` on every static shape (the master elbows, all spine bands, sub-strips). It disables an internal high-DPI offscreen pass — these shapes do not need it because they have no stroke.
- Group static decoration into a single `<Layer listening={false} />`. Interactive controls go on a separate `<Layer />`. Konva will only re-render the interactive layer on hover.
- Cache the `<Layer />` of static decoration after first paint: `layerRef.current.cache()`. Re-cache on resize, not on hover.
- DevicePixelRatio: set the stage `pixelRatio={Math.min(2, window.devicePixelRatio)}`. Above 2× there are no perceivable gains for flat color.

### 12.4 Font loading

Embed Jura, Big Shoulders Display, and DM Mono via `@font-face`. Load them with `document.fonts.ready` **before** the first Konva paint — Konva measures text on creation and will mis-position labels if the font isn't ready.

### 12.5 Hit testing

For each `<Band>` / `<Stadium>`, render an invisible DOM `<button>` at the same screen rect (`position: absolute; opacity: 0;`). The canvas is purely visual. This solves accessibility, keyboard navigation, and focus rings in one move.

---

## 13. Deliverable order for the implementing engineer

1. **Tokens file** — port §2 to your design-tokens system (`tokens.lcars.ts`).
2. **Primitives** — implement `Elbow`, `Stadium`, `CapLeft`, `CapRight`, `Band` as a separate package. Test them in isolation against `lcars_reference.png` — sub-pixel match.
3. **Layout schema** — encode the current Memex screen as a `Schema` JSON (§8).
4. **Render** — write the canvas renderer that walks the schema and emits primitives.
5. **DOM accessibility shadow** — for each interactive shape, position an `<a11y-button>` over it.
6. **State wiring** — connect to existing chat state, planner state, model state, ctx state.
7. **Motion** — implement the 5 motion entries in §7. Nothing else.
8. **Reduced-motion fallback** — verify `prefers-reduced-motion: reduce` kills the ticker and radar.
9. **Verify against reference** — overlay your build over `lcars_reference.png` at 50 % opacity. Elbows should align within 2 px. Spine band heights should fall on the same proportions.

---

## 14. Definition of done

- All four primitives render pixel-clean (no anti-aliased inner corners, no stroke artifacts).
- Spine bands fill the available vertical gap exactly — no slack, no overlap, between elbows.
- No animation persists when `prefers-reduced-motion: reduce` is set.
- Lighthouse a11y score ≥ 95 for the shell route.
- All canvas text is mirrored by an offscreen DOM accessibility tree.
- The screen looks **still** at first glance. If a teammate sees it from across the room and asks "is something loading?", the motion is wrong.

---

*Reference assets:*

- `lcars_philosophy.md` — the design philosophy this spec implements.
- `lcars_reference.png` — the pixel-clean target. Engineers should overlay their build on this image and check fit.
