"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { usePalaceColors, type PalaceColorTokens } from "@/lib/palace/theme-materials";

/**
 * Theme-specific ambient particle system using InstancedMesh.
 * Each motif gets different particle behaviour:
 *   forge   — slow-rising ember sparks
 *   slab    — gentle falling dust motes
 *   signal  — horizontal data-stream dashes
 *   grid    — precise upward dots in columns
 *   terminal— falling green "rain" characters
 *   lcars   — lamport arcs around center
 *   neon    — chaotic fast-moving neon sparks
 *   gallery — rare, slow floating dust
 *
 * Cost: single InstancedMesh draw call, ~200-400 particles, <0.5ms/frame.
 */

interface ParticleConfig {
  count: number;
  speed: number;
  spread: [number, number, number]; // x, y, z range
  direction: [number, number, number]; // primary drift direction
  sizeRange: [number, number];
  wobble: number; // lateral oscillation strength
  brightness: number; // emissive factor
}

const MOTIF_PARTICLES: Record<string, ParticleConfig> = {
  forge: {
    count: 280,
    speed: 0.4,
    spread: [10, 6, 10],
    direction: [0, 1, 0],
    sizeRange: [0.015, 0.04],
    wobble: 0.8,
    brightness: 1.2,
  },
  slab: {
    count: 140,
    speed: 0.15,
    spread: [12, 6, 10],
    direction: [0, -1, 0],
    sizeRange: [0.01, 0.025],
    wobble: 0.4,
    brightness: 0.4,
  },
  signal: {
    count: 190,
    speed: 0.6,
    spread: [14, 4, 10],
    direction: [1, 0.1, 0],
    sizeRange: [0.008, 0.02],
    wobble: 0.2,
    brightness: 0.9,
  },
  grid: {
    count: 120,
    speed: 0.25,
    spread: [8, 5, 8],
    direction: [0, 1, 0],
    sizeRange: [0.01, 0.015],
    wobble: 0.1,
    brightness: 0.5,
  },
  terminal: {
    count: 420,
    speed: 1.2,
    spread: [14, 8, 10],
    direction: [0, -1, 0],
    sizeRange: [0.008, 0.03],
    wobble: 0.05,
    brightness: 1.3,
  },
  lcars: {
    count: 165,
    speed: 0.35,
    spread: [8, 4, 8],
    direction: [0.5, 0.3, 0],
    sizeRange: [0.012, 0.03],
    wobble: 1.2,
    brightness: 0.7,
  },
  neon: {
    count: 325,
    speed: 1.0,
    spread: [12, 5, 10],
    direction: [0.2, 0.5, 0],
    sizeRange: [0.01, 0.035],
    wobble: 1.5,
    brightness: 1.4,
  },
  gallery: {
    count: 65,
    speed: 0.08,
    spread: [10, 5, 10],
    direction: [0, 0.3, 0],
    sizeRange: [0.008, 0.018],
    wobble: 0.3,
    brightness: 0.25,
  },
};

// Per-particle state stored in typed arrays for performance
interface ParticleState {
  positions: Float32Array;
  velocities: Float32Array;
  phases: Float32Array;   // random phase offsets
  sizes: Float32Array;
  lifetimes: Float32Array; // 0-1 cycle position
}

function initParticles(config: ParticleConfig): ParticleState {
  const n = config.count;
  const positions = new Float32Array(n * 3);
  const velocities = new Float32Array(n * 3);
  const phases = new Float32Array(n);
  const sizes = new Float32Array(n);
  const lifetimes = new Float32Array(n);

  for (let i = 0; i < n; i++) {
    const i3 = i * 3;
    // Random starting position within spread
    positions[i3] = (Math.random() - 0.5) * config.spread[0];
    positions[i3 + 1] = Math.random() * config.spread[1];
    positions[i3 + 2] = (Math.random() - 0.5) * config.spread[2] - 2;

    // Base velocity from direction + small random variance
    velocities[i3] = config.direction[0] * config.speed + (Math.random() - 0.5) * 0.1;
    velocities[i3 + 1] = config.direction[1] * config.speed + (Math.random() - 0.5) * 0.05;
    velocities[i3 + 2] = config.direction[2] * config.speed + (Math.random() - 0.5) * 0.1;

    phases[i] = Math.random() * Math.PI * 2;
    sizes[i] = config.sizeRange[0] + Math.random() * (config.sizeRange[1] - config.sizeRange[0]);
    lifetimes[i] = Math.random(); // stagger start
  }

  return { positions, velocities, phases, sizes, lifetimes };
}

const _tempObj = new THREE.Object3D();
const _tempColor = new THREE.Color();

export function AmbientParticles({ level }: { level: "lobby" | "wing" | "hall" | "room" }) {
  const colors = usePalaceColors();
  const meshRef = useRef<THREE.InstancedMesh>(null);

  const config = MOTIF_PARTICLES[colors.motif] ?? MOTIF_PARTICLES.slab;
  const isTerminal = colors.motif === "terminal";

  // Scale count by level depth
  const levelScale = level === "lobby" ? 1 : level === "wing" ? 0.8 : 0.6;
  const count = Math.floor(config.count * levelScale);

  const state = useMemo(() => initParticles({ ...config, count }), [colors.motif, count]);

  // Set up instance colors once
  useMemo(() => {
    if (!meshRef.current) return;
    const accentCol = new THREE.Color(colors.accent);
    const accent2Col = new THREE.Color(colors.accent2 ?? colors.accentStrong);

    for (let i = 0; i < count; i++) {
      // Alternate between accent colors with slight variation
      const blend = Math.random();
      _tempColor.copy(accentCol).lerp(accent2Col, blend);
      const hsl = { h: 0, s: 0, l: 0 };
      _tempColor.getHSL(hsl);
      if (colors.isLight) {
        // For light themes: darken particles and increase saturation for visibility
        _tempColor.setHSL(hsl.h, Math.min(hsl.s * 1.6, 1), Math.min(hsl.l * 0.5, 0.4));
      } else if (isTerminal) {
        // Matrix rain: vary brightness per particle — some bright heads, some dim trails
        const brightnessVar = 0.4 + Math.random() * 0.6; // 0.4 to 1.0
        _tempColor.setHSL(hsl.h, Math.min(hsl.s * 1.3, 1), hsl.l * brightnessVar);
      } else {
        // Dark themes: boost saturation slightly
        _tempColor.setHSL(hsl.h, Math.min(hsl.s * 1.2, 1), hsl.l);
      }
      meshRef.current.setColorAt(i, _tempColor);
    }
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }
  }, [colors.motif, colors.accent, colors.accent2, colors.accentStrong, colors.isLight, count]);

  useFrame((frameState, delta) => {
    if (!meshRef.current) return;
    const t = frameState.clock.elapsedTime;

    for (let i = 0; i < count; i++) {
      const i3 = i * 3;

      // Advance position
      state.positions[i3] += state.velocities[i3] * delta;
      state.positions[i3 + 1] += state.velocities[i3 + 1] * delta;
      state.positions[i3 + 2] += state.velocities[i3 + 2] * delta;

      // Wobble (lateral oscillation)
      state.positions[i3] += Math.sin(t * 1.5 + state.phases[i]) * config.wobble * delta;
      state.positions[i3 + 2] += Math.cos(t * 1.2 + state.phases[i] * 0.7) * config.wobble * 0.5 * delta;

      // Advance lifetime
      state.lifetimes[i] += delta * 0.15;

      // Wrap particles that go out of bounds
      const halfX = config.spread[0] / 2;
      const halfZ = config.spread[2] / 2;
      if (state.positions[i3] > halfX) state.positions[i3] = -halfX;
      if (state.positions[i3] < -halfX) state.positions[i3] = halfX;
      if (state.positions[i3 + 1] > config.spread[1]) {
        state.positions[i3 + 1] = 0;
        state.lifetimes[i] = 0;
      }
      if (state.positions[i3 + 1] < 0) {
        state.positions[i3 + 1] = config.spread[1];
        state.lifetimes[i] = 0;
      }
      if (state.positions[i3 + 2] > halfZ - 2) state.positions[i3 + 2] = -halfZ - 2;
      if (state.positions[i3 + 2] < -halfZ - 2) state.positions[i3 + 2] = halfZ - 2;

      // Fade in/out based on lifetime for smooth appearance
      const life = state.lifetimes[i] % 1;
      const fade = life < 0.1 ? life / 0.1 : life > 0.9 ? (1 - life) / 0.1 : 1;
      const s = state.sizes[i] * fade;

      _tempObj.position.set(
        state.positions[i3],
        state.positions[i3 + 1],
        state.positions[i3 + 2],
      );
      // Terminal motif: elongate particles vertically for Matrix rain streak effect
      if (isTerminal) {
        _tempObj.scale.set(s * 0.4, s * 3.5, s * 0.4);
      } else {
        _tempObj.scale.setScalar(s);
      }
      _tempObj.updateMatrix();
      meshRef.current.setMatrixAt(i, _tempObj.matrix);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  // For light themes, reduce emissive and increase opacity for solid-looking particles
  const effectiveBrightness = colors.isLight ? config.brightness * 0.3 : config.brightness;
  const effectiveOpacity = colors.isLight ? 0.85 : 0.7;

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]} frustumCulled={false}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshPhysicalMaterial
        color={colors.accent}
        emissive={colors.accent}
        emissiveIntensity={effectiveBrightness}
        transparent
        opacity={effectiveOpacity}
        depthWrite={false}
        toneMapped={false}
      />
    </instancedMesh>
  );
}
