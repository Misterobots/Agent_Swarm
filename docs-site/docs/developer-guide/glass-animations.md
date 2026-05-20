---
title: Glass Animation System
---

# Glass Animation System

A set of CSS keyframes and React patterns that produce one-shot glassomorphic sweep effects on state transitions across the Memex UI.

## Overview

The system is defined in `ui/src/app/globals.css` and is available globally — no imports needed in component files. It provides three keyframe animations and four utility classes.

### Design intent

- **One-shot only** — sweeps fire once per transition and self-clean via `onAnimationEnd`. They never loop.
- **No external libraries** — pure CSS keyframes + React state (`useState` / `useRef` / `useEffect`).
- **Reduced-motion safe** — the existing `@media (prefers-reduced-motion: reduce)` block in `globals.css` collapses all durations to `0.01ms`, effectively disabling the animations for users who prefer it.

---

## CSS Classes

### `.glass-sweep-shimmer`

A diagonal shimmer overlay that sweeps left-to-right across its container. Place it as a direct child of a `position: relative; overflow: hidden` element.

```css
.glass-sweep-shimmer {
  position: absolute;
  inset: 0 auto 0 0;
  width: 55%;
  background: linear-gradient(
    105deg,
    transparent 0%,
    rgba(255,255,255,0.03) 25%,
    rgba(255,255,255,0.10) 50%,
    rgba(255,255,255,0.03) 75%,
    transparent 100%
  );
  animation: glass-sweep 0.85s cubic-bezier(0.4, 0, 0.2, 1) 1 forwards;
  pointer-events: none;
  will-change: transform;
}
```

Keyframe: `glass-sweep` — translates from −140% to +340% with a −18° skew.

### `.glass-surface`

Frosted glass base for panels and cards.

```css
.glass-surface {
  background: rgba(255, 255, 255, 0.025);
  backdrop-filter: blur(18px) saturate(1.4);
  -webkit-backdrop-filter: blur(18px) saturate(1.4);
  border: 1px solid rgba(255, 255, 255, 0.07);
}
```

Use this on panel containers where you want a frosted-glass look. Combine with theme border tokens for the full effect:

```tsx
<div className="glass-surface border-l border-[var(--border)] shadow-2xl">
```

### `.glass-panel-enter`

One-shot slide-in for panels appearing from the right.

```css
.glass-panel-enter {
  animation: glass-panel-enter 0.32s cubic-bezier(0.22, 1, 0.36, 1) 1 both;
}
```

Keyframe: fades in + translates from +20 px to 0 with a slight −2 px overshoot at 60%.

### `.glass-row-enter`

One-shot fade-down for list rows.

```css
.glass-row-enter {
  animation: glass-row-enter 0.22s ease-out 1 both;
}
```

Keyframe: fades in from 0% opacity + translates from −4 px to 0.

---

## React Pattern: Transition-Triggered Sweep

The sweep renders only while a boolean state is `true`, then clears itself via `onAnimationEnd`.

```tsx
import { useEffect, useRef, useState } from "react";

// Detect a specific status transition and fire the sweep
const [sweeping, setSweeping] = useState(false);
const prevStatus = useRef(status);

useEffect(() => {
  const prev = prevStatus.current;
  if (prev !== status && (status === "in_progress" || status === "completed")) {
    setSweeping(true);
  }
  prevStatus.current = status;
}, [status]);

// In JSX — container must be position:relative + overflow:hidden
<div
  className="relative overflow-hidden ..."
  onAnimationEnd={() => setSweeping(false)}
>
  {sweeping && <div className="glass-sweep-shimmer" />}
  {/* ... rest of content */}
</div>
```

!!! note "`onAnimationEnd` placement"
    Place `onAnimationEnd` on the **container**, not on the shimmer div itself. The shimmer is removed from the DOM when `sweeping` becomes false, which happens when the container's `animationend` fires.

---

## React Pattern: Panel Open Sweep

For a panel that slides in, fire a full-panel sweep when `panelOpen` transitions from `false` to `true`.

```tsx
const [panelSweeping, setPanelSweeping] = useState(false);
const prevOpen = useRef(panelOpen);

useEffect(() => {
  if (!prevOpen.current && panelOpen) {
    setPanelSweeping(true);
  }
  prevOpen.current = panelOpen;
}, [panelOpen]);

// In JSX — inside the panel container
{panelSweeping && (
  <div
    className="absolute inset-0 overflow-hidden pointer-events-none z-10"
    onAnimationEnd={() => setPanelSweeping(false)}
  >
    <div className="glass-sweep-shimmer" style={{ width: "70%" }} />
  </div>
)}
```

The `width: "70%"` override makes the shimmer cover most of a narrow panel. For wider surfaces, use the default 55% or adjust as needed.

---

## Staggered Row Entry

Wrap each row in a `glass-row-enter` div with a per-index `animationDelay` for a cascade effect:

```tsx
{steps.map((step, idx) => (
  <div
    key={step.id}
    className="glass-row-enter"
    style={{ animationDelay: `${idx * 40}ms` }}
  >
    <StepRow step={step} />
  </div>
))}
```

40 ms per step feels natural up to ~10 rows. For longer lists, reduce to 20–25 ms.

---

## Applying to New Components

Checklist when adding the sweep to a new component:

1. **Container**: add `relative overflow-hidden` to the element that clips the shimmer.
2. **State**: add `const [sweeping, setSweeping] = useState(false)` and a `useRef` tracking the previous value of whatever prop drives the transition.
3. **Effect**: call `setSweeping(true)` inside a `useEffect` when the transition condition is met.
4. **JSX**: render `{sweeping && <div className="glass-sweep-shimmer" />}` as the first child.
5. **Cleanup**: attach `onAnimationEnd={() => setSweeping(false)}` to the container (not the shimmer child).
6. **Glass surface (optional)**: add `glass-surface` to the container if you also want the frosted-glass base.

---

## Existing Usages

| Component | File | Trigger |
|-----------|------|---------|
| `GoalStepRow` | `ui/src/components/goals/GoalStepRow.tsx` | `pending → in_progress` or `pending → completed` |
| `GoalsPanel` (row entry) | `ui/src/components/goals/GoalsPanel.tsx` | Panel open — staggered per step index |
| `GoalsPanel` (panel sweep) | `ui/src/components/goals/GoalsPanel.tsx` | `panelOpen` transitions `false → true` |

---

## Source of Truth

| What | File |
|------|------|
| Keyframes and utility classes | `ui/src/app/globals.css` — bottom section `GLASSOMORPHIC SWEEP SYSTEM` |
| Step row usage | `ui/src/components/goals/GoalStepRow.tsx` |
| Panel usage | `ui/src/components/goals/GoalsPanel.tsx` |
