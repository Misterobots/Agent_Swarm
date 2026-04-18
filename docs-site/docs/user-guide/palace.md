---
title: Memory Palace
---

# Memory Palace

A 3D spatial interface for exploring, navigating, and managing AI agent memories. The Palace renders a navigable hierarchy — lobby → wings → halls → rooms → drawers — using WebGL via React Three Fiber.

## How to Access

- **UI**: Click **Palace** in the Hive Mind sidebar
- **URL**: `http://localhost:3005/palace`

## Navigation Hierarchy

| Level | Description | Visual |
|-------|-------------|--------|
| **Lobby** | Entry point showing all wings | Archways with wing names and hall counts |
| **Wing** | Collection of halls for a domain | Corridor with door panels for each hall |
| **Hall** | Group of related rooms | — |
| **Room** | Contains memory drawers | Room title, drawer count, 3D drawer meshes |

Click on archways, doors, or drawers to descend. Use the **← back button** or press **Esc** to ascend. The breadcrumb bar always shows your current position.

## Visual Enhancements

### Entrance Animation
On first load, the camera performs a dramatic 2.2-second swoop from an elevated position down to the lobby floor, using a cubic ease-out curve.

### Breathing Camera
The camera gently bobs vertically (0.008 amplitude at 0.4 Hz) with a slight horizontal sway (0.003), creating an organic feel rather than a static viewport.

### Parallax & Roll
Mouse movement applies ±3.7° tilt and ±0.008 roll to the camera, giving subtle depth parallax as you move the cursor.

### Scene Transitions
Navigating between levels triggers a 0.7-second fade overlay with a bell-curve opacity envelope, smoothly masking the scene swap.

### Ambient Particles
Theme-adaptive InstancedMesh particles fill the scene. Each theme motif defines its own count, color, speed, and drift direction:

| Motif | Particles | Behavior |
|-------|-----------|----------|
| Forge (ember) | 120 | Rising sparks, warm orange |
| Terminal (hacker) | 420 | Matrix digital rain — vertically elongated 3.5× streaks, brightness variation per particle for cascade effect, near-zero wobble |
| Neon (cyberpunk) | 140 | Chaotic multicolor drift |
| Gallery (minimal) | 25 | Slow, sparse dust motes |
| LCARS (star-trek) | 80 | Horizontal data streams |
| Snow (slate) | 180 | Gentle snowfall with lateral drift |
| Signal | 100 | Clean accent-colored particles |

### Volumetric Light Cones
Animated light cone meshes simulate visible light volume. In the lobby, wide shafts sweep slowly; in rooms, focused downlights illuminate drawer areas. Opacity pulses with a sine wave.

### Glassmorphism HUD
All 2D overlay elements use frosted-glass styling:

- `backdrop-filter: blur(16px) saturate(1.4)`
- Semi-transparent backgrounds with subtle borders
- Applied to: breadcrumb bar, back button, search bar, search results, memory count badge

### Memory-Aware Drawers
Each drawer mesh in a room communicates metadata at a glance:

- **Domain hue**: Handle color derived from the memory's domain via hash
- **Type icon**: Emoji indicator on the face (💬 chat, ⟨⟩ code, ⚠ warning, ◆ episodic, ☐ semantic, ◎ procedural)
- **Access bar**: Bottom strip scales with access frequency (0–20+)
- **Age desaturation**: Older memories fade to 60% saturation
- **Emissive glow**: Frequently-accessed drawers glow brighter
- **Search dimming**: Non-matching drawers dim to 35% opacity during search

### Detail Panel
Clicking a drawer opens a right-slide panel with:

- Memory type badge and domain label
- Full content text
- Metadata grid (agent, owner, created date, access count, wing)
- Change history accordion
- Spring-curve slide animation (`cubic-bezier(0.16, 1, 0.3, 1)`)
- Glassmorphism background with 20px blur

## Theme Integration

The Palace reads CSS variables from the active theme motif via a `MutationObserver` on `data-theme`. All 8 motifs are supported:

- **forge** (ember) — warm oranges, rising sparks
- **slab** (slate) — cool grays, stone aesthetic
- **signal** — accent-driven, clean
- **grid** (office) — structured, neutral
- **terminal** (hacker) — Matrix theme: pure black `#000000` backgrounds, Matrix green `#00FF41` text/accents, enhanced scanlines with `rgba(0,255,65,0.025)`, dual drop-shadow CRT glow, intensified logo pulse, 420 digital rain particles
- **lcars** (star-trek) — panels, data streams
- **neon** (cyberpunk) — vivid magentas and cyans
- **gallery** (minimal) — sparse, white-space focused

## Search

Type in the search bar to filter memories across the entire Palace. Matching drawers remain fully visible; non-matches dim. Clear the search to restore all drawers.

## Technical Stack

| Component | Version |
|-----------|---------|
| React Three Fiber | 9.5.0 |
| @react-three/drei | 10.7.7 |
| Three.js | 0.183.2 |
| @react-three/postprocessing | 3.0.4 |
| Zustand | 5.0.12 |

Post-processing pipeline: Bloom → N8AO ambient occlusion → Vignette → ACES filmic tone mapping.

Adaptive device pixel ratio: `[1, 1.5]` for performance on lower-end GPUs.
