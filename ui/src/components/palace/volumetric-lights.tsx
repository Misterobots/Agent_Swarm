"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { usePalaceColors } from "@/lib/palace/theme-materials";

/**
 * Simulated volumetric light shafts — semi-transparent cone meshes
 * positioned at key light sources. Creates the illusion of visible
 * light volume in the architectural space.
 *
 * Uses ConeGeometry with high-transmission MeshPhysicalMaterial.
 * Slow sine-wave opacity animation for "shifting light" effect.
 *
 * Cost: 3 draw calls, ~0.2ms/frame.
 */

export function VolumetricLights({ level }: { level: "lobby" | "wing" | "hall" | "room" }) {
  const colors = usePalaceColors();
  const shaft1 = useRef<THREE.Mesh>(null);
  const shaft2 = useRef<THREE.Mesh>(null);
  const shaft3 = useRef<THREE.Mesh>(null);
  const shaft4 = useRef<THREE.Mesh>(null);
  const shaft5 = useRef<THREE.Mesh>(null);

  const isRoom = level === "hall" || level === "room";

  useFrame((state) => {
    const t = state.clock.elapsedTime;

    const refs = [shaft1, shaft2, shaft3, shaft4, shaft5];
    refs.forEach((ref, idx) => {
      if (!ref.current) return;
      const mat = ref.current.material as THREE.MeshPhysicalMaterial;
      const phase = idx * 0.9;
      const base = isRoom ? 0.06 : 0.08;
      const amp = isRoom ? 0.025 : 0.035;
      mat.opacity = base + Math.sin(t * 0.5 + phase) * amp;

      // Very subtle rotation for light-shifting effect
      ref.current.rotation.z = Math.sin(t * 0.15 + phase) * 0.03;
    });
  });

  if (isRoom) {
    // Room: single central shaft + two side washes
    return (
      <group>
        {/* Central downlight shaft */}
        <mesh ref={shaft1} position={[0, 2.8, -1.5]} rotation={[0, 0, 0]}>
          <coneGeometry args={[1.2, 3.5, 32, 1, true]} />
          <meshPhysicalMaterial
            color={colors.glowSoft ?? colors.accent}
            emissive={colors.glowSoft ?? colors.accent}
            emissiveIntensity={0.15}
            transparent
            opacity={0.05}
            depthWrite={false}
            side={THREE.DoubleSide}
            roughness={1}
          />
        </mesh>

        {/* Left wall wash */}
        <mesh ref={shaft2} position={[-2.8, 2.5, -2]} rotation={[0, 0, 0.3]}>
          <coneGeometry args={[0.6, 2.8, 16, 1, true]} />
          <meshPhysicalMaterial
            color={colors.accent}
            emissive={colors.accent}
            emissiveIntensity={0.1}
            transparent
            opacity={0.04}
            depthWrite={false}
            side={THREE.DoubleSide}
            roughness={1}
          />
        </mesh>

        {/* Right wall wash */}
        <mesh ref={shaft3} position={[2.8, 2.5, -2]} rotation={[0, 0, -0.3]}>
          <coneGeometry args={[0.6, 2.8, 16, 1, true]} />
          <meshPhysicalMaterial
            color={colors.accent2 ?? colors.accent}
            emissive={colors.accent2 ?? colors.accent}
            emissiveIntensity={0.1}
            transparent
            opacity={0.04}
            depthWrite={false}
            side={THREE.DoubleSide}
            roughness={1}
          />
        </mesh>
      </group>
    );
  }

  // Lobby/Wing: wider atmospheric shafts from above
  return (
    <group>
      {/* Main overhead shaft */}
      <mesh ref={shaft1} position={[0, 3.5, -1]} rotation={[0, 0, 0]}>
        <coneGeometry args={[2.5, 5, 32, 1, true]} />
        <meshPhysicalMaterial
          color={colors.glowSoft ?? colors.accent}
          emissive={colors.glowSoft ?? colors.accent}
          emissiveIntensity={0.12}
          transparent
          opacity={0.08}
          depthWrite={false}
          side={THREE.DoubleSide}
          roughness={1}
        />
      </mesh>

      {/* Left diagonal shaft */}
      <mesh ref={shaft2} position={[-4, 3.8, -3]} rotation={[0.15, 0, 0.25]}>
        <coneGeometry args={[1.4, 4.5, 24, 1, true]} />
        <meshPhysicalMaterial
          color={colors.accent}
          emissive={colors.accent}
          emissiveIntensity={0.08}
          transparent
          opacity={0.06}
          depthWrite={false}
          side={THREE.DoubleSide}
          roughness={1}
        />
      </mesh>

      {/* Right diagonal shaft */}
      <mesh ref={shaft3} position={[4, 3.6, -2.5]} rotation={[-0.1, 0, -0.2]}>
        <coneGeometry args={[1.2, 4, 24, 1, true]} />
        <meshPhysicalMaterial
          color={colors.accent2 ?? colors.accentStrong}
          emissive={colors.accent2 ?? colors.accentStrong}
          emissiveIntensity={0.08}
          transparent
          opacity={0.06}
          depthWrite={false}
          side={THREE.DoubleSide}
          roughness={1}
        />
      </mesh>

      {/* Far-left sweeping shaft */}
      <mesh ref={shaft4} position={[-6, 4.2, -5]} rotation={[0.2, 0, 0.35]}>
        <coneGeometry args={[1.0, 4, 20, 1, true]} />
        <meshPhysicalMaterial
          color={colors.glowSoft ?? colors.accent}
          emissive={colors.glowSoft ?? colors.accent}
          emissiveIntensity={0.06}
          transparent
          opacity={0.04}
          depthWrite={false}
          side={THREE.DoubleSide}
          roughness={1}
        />
      </mesh>

      {/* Far-right sweeping shaft */}
      <mesh ref={shaft5} position={[6, 4, -4.5]} rotation={[-0.15, 0, -0.3]}>
        <coneGeometry args={[0.9, 3.8, 20, 1, true]} />
        <meshPhysicalMaterial
          color={colors.accent2 ?? colors.accent}
          emissive={colors.accent2 ?? colors.accent}
          emissiveIntensity={0.06}
          transparent
          opacity={0.04}
          depthWrite={false}
          side={THREE.DoubleSide}
          roughness={1}
        />
      </mesh>
    </group>
  );
}
