"use client";

import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { AmbientParticles } from "./ambient-particles";

/**
 * Lightweight transparent R3F canvas that renders ONLY atmospheric particles.
 * No geometry, no shadows, no post-processing — just floating particles
 * that drift through the CSS 3D spatial interface.
 */
export function AtmosphereCanvas() {
  const level = usePalaceStore((s) => s.location.level) as
    | "lobby"
    | "wing"
    | "hall"
    | "room";

  return (
    <Canvas
      style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }}
      gl={{ alpha: true, antialias: false, powerPreference: "default" }}
      camera={{ position: [0, 2, 6], fov: 60, near: 0.1, far: 50 }}
      dpr={[1, 1.5]}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.5} />
        <AmbientParticles level={level} />
      </Suspense>
    </Canvas>
  );
}
