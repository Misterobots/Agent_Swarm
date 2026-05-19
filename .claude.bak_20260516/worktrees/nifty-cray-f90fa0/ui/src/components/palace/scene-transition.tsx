"use client";

import { useRef, useEffect, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { usePalaceStore, type PalaceLevel } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";

/**
 * Scene transition overlay — renders a full-screen quad that fades in/out
 * when navigating between palace levels. Creates a subtle radial wipe
 * with accent coloring instead of a hard scene-swap "pop".
 *
 * Duration: ~0.7s total (0.35s fade-out + 0.35s fade-in)
 * Cost: one transparent quad, no render targets needed.
 */

const TRANSITION_DURATION = 0.7; // seconds total
const HALF_DUR = TRANSITION_DURATION / 2;

export function SceneTransition() {
  const colors = usePalaceColors();
  const location = usePalaceStore((s) => s.location);
  const meshRef = useRef<THREE.Mesh>(null);
  const progressRef = useRef(0);
  const activeRef = useRef(false);
  const prevLevel = useRef<PalaceLevel>(location.level);

  // Detect level changes
  useEffect(() => {
    if (location.level !== prevLevel.current) {
      prevLevel.current = location.level;
      activeRef.current = true;
      progressRef.current = 0;
    }
  }, [location.level]);

  useFrame((state, delta) => {
    if (!meshRef.current) return;
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;

    if (activeRef.current) {
      progressRef.current += delta;
      const t = progressRef.current / TRANSITION_DURATION;

      if (t >= 1) {
        // Transition complete
        activeRef.current = false;
        mat.opacity = 0;
        return;
      }

      // Bell curve: peaks at 0.5, zero at 0 and 1
      // Smooth envelope: sin(pi * t)
      const envelope = Math.sin(Math.PI * t);
      mat.opacity = envelope * 0.65; // max 65% opacity at peak
    } else {
      // Ensure invisible when not transitioning
      if (mat.opacity > 0.001) {
        mat.opacity *= 0.85; // quick fade residual
      }
    }
  });

  return (
    <mesh ref={meshRef} position={[0, 0, 0.1]} renderOrder={999}>
      <planeGeometry args={[100, 100]} />
      <meshBasicMaterial
        color={colors.shadow ?? colors.bg}
        transparent
        opacity={0}
        depthTest={false}
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}
