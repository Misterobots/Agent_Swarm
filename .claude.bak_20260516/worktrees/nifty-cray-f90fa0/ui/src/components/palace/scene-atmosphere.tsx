"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import * as THREE from "three";
import { usePalaceColors } from "@/lib/palace/theme-materials";

export function SceneAtmosphere({ level }: { level: "lobby" | "wing" | "hall" | "room" }) {
  const colors = usePalaceColors();
  const pulseRefs = useRef<THREE.Mesh[]>([]);
  const ringRefs = useRef<THREE.Mesh[]>([]);

  const density = level === "lobby" ? 1 : level === "wing" ? 0.82 : 0.68;

  const accents = useMemo(
    () => [
      { position: [-6.5, 2.6, -7.5] as [number, number, number], scale: [0.28, 4.6, 0.2] as [number, number, number], speed: 0.9 },
      { position: [6.5, 2.2, -7.8] as [number, number, number], scale: [0.24, 3.8, 0.2] as [number, number, number], speed: 1.15 },
      { position: [0, 4.4, -9.5] as [number, number, number], scale: [7.5, 0.18, 0.18] as [number, number, number], speed: 0.7 },
    ],
    [],
  );

  const motifElements = useMemo(() => {
    switch (colors.motif) {
      case "forge":
        return (
          <>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.018, -2]}>
              <ringGeometry args={[2.6, 5.9, 64]} />
              <meshPhysicalMaterial color={colors.accentStrong} emissive={colors.accentStrong} emissiveIntensity={0.15} transparent opacity={0.15 * density} depthWrite={false} roughness={0.2} metalness={0.5} />
            </mesh>
            <mesh position={[0, 4.1, -8.7]}>
              <planeGeometry args={[9.5, 1.8]} />
              <meshPhysicalMaterial color={colors.mist} emissive={colors.mist} emissiveIntensity={0.08} transparent opacity={0.09 * density} depthWrite={false} />
            </mesh>
          </>
        );
      case "slab":
        return (
          <>
            <mesh position={[-8.8, 2.2, -8.8]} castShadow>
              <cylinderGeometry args={[0.2, 0.25, 4.6, 16]} />
              <meshPhysicalMaterial color={colors.trim} roughness={0.25} metalness={0.5} clearcoat={0.7} transparent opacity={0.2 * density} />
            </mesh>
            <mesh position={[8.8, 2.2, -8.8]} castShadow>
              <cylinderGeometry args={[0.2, 0.25, 4.6, 16]} />
              <meshPhysicalMaterial color={colors.trim} roughness={0.25} metalness={0.5} clearcoat={0.7} transparent opacity={0.2 * density} />
            </mesh>
          </>
        );
      case "signal":
        return (
          <>
            {[-7, -2.2, 2.2, 7].map((x, idx) => (
              <mesh key={x} position={[x, 3.3, -8.2]} castShadow>
                <capsuleGeometry args={[0.07, 1.2 + idx * 0.25, 4, 12]} />
                <meshPhysicalMaterial color={idx % 2 === 0 ? colors.accent : colors.accent2} emissive={idx % 2 === 0 ? colors.accent : colors.accent2} emissiveIntensity={0.3} transparent opacity={0.22 * density} depthWrite={false} roughness={0.1} metalness={0.3} />
              </mesh>
            ))}
          </>
        );
      case "grid":
        return (
          <>
            {Array.from({ length: 5 }).map((_, i) => (
              <mesh key={`grid-x-${i}`} position={[-6 + i * 3, 1.6, -9.2]} castShadow>
                <cylinderGeometry args={[0.02, 0.02, 3.1, 8]} />
                <meshPhysicalMaterial color={colors.border} emissive={colors.border} emissiveIntensity={0.15} transparent opacity={0.2 * density} depthWrite={false} roughness={0.1} metalness={0.6} />
              </mesh>
            ))}
          </>
        );
      case "terminal":
        return (
          <>
            <mesh position={[0, 2.4, -8.8]}>
              <planeGeometry args={[11.5, 2.6]} />
              <meshPhysicalMaterial color={colors.glowSoft} emissive={colors.glowSoft} emissiveIntensity={0.15} transparent opacity={0.08 * density} depthWrite={false} />
            </mesh>
            {[-4, 0, 4].map((x) => (
              <mesh key={x} position={[x, 2.4, -8.75]} castShadow>
                <cylinderGeometry args={[0.03, 0.03, 2.3, 8]} />
                <meshPhysicalMaterial color={colors.accent} emissive={colors.accent} emissiveIntensity={0.4} transparent opacity={0.22 * density} depthWrite={false} roughness={0.1} />
              </mesh>
            ))}
          </>
        );
      case "lcars":
        return (
          <>
            <mesh position={[-8.2, 2.55, -7.8]}>
              <capsuleGeometry args={[0.62, 3.6, 6, 20]} />
              <meshPhysicalMaterial color={colors.accent2} emissive={colors.accent2} emissiveIntensity={0.2} transparent opacity={0.28 * density} depthWrite={false} roughness={0.15} metalness={0.3} clearcoat={0.8} />
            </mesh>
            <mesh position={[8.1, 2.15, -7.7]}>
              <capsuleGeometry args={[0.5, 3.05, 6, 20]} />
              <meshPhysicalMaterial color={colors.accentStrong} emissive={colors.accentStrong} emissiveIntensity={0.2} transparent opacity={0.28 * density} depthWrite={false} roughness={0.15} metalness={0.3} clearcoat={0.8} />
            </mesh>
            <mesh position={[0, 4.35, -8.15]} rotation={[0, 0, Math.PI / 2]}>
              <capsuleGeometry args={[0.18, 5.8, 4, 16]} />
              <meshPhysicalMaterial color={colors.trim} emissive={colors.trim} emissiveIntensity={0.15} transparent opacity={0.2 * density} depthWrite={false} roughness={0.2} metalness={0.4} />
            </mesh>
            <mesh position={[0, 3.45, -8.05]}>
              <planeGeometry args={[6.6, 0.42]} />
              <meshPhysicalMaterial color={colors.glowSoft} emissive={colors.glowSoft} emissiveIntensity={0.2} transparent opacity={0.12 * density} depthWrite={false} />
            </mesh>
          </>
        );
      case "neon":
        return (
          <>
            <mesh rotation={[0, 0, Math.PI / 8]} position={[-6.8, 3.1, -8.2]}>
              <capsuleGeometry args={[0.06, 3.8, 4, 12]} />
              <meshPhysicalMaterial color={colors.accent} emissive={colors.accent} emissiveIntensity={0.6} transparent opacity={0.25 * density} depthWrite={false} roughness={0.08} />
            </mesh>
            <mesh rotation={[0, 0, -Math.PI / 8]} position={[6.8, 2.9, -8.2]}>
              <capsuleGeometry args={[0.06, 3.8, 4, 12]} />
              <meshPhysicalMaterial color={colors.accent2} emissive={colors.accent2} emissiveIntensity={0.6} transparent opacity={0.25 * density} depthWrite={false} roughness={0.08} />
            </mesh>
            <mesh position={[0, 4.25, -8.9]}>
              <capsuleGeometry args={[0.04, 8.2, 4, 12]} />
              <meshPhysicalMaterial color={colors.accentStrong} emissive={colors.accentStrong} emissiveIntensity={0.7} transparent opacity={0.28 * density} depthWrite={false} roughness={0.05} />
            </mesh>
          </>
        );
      case "gallery":
        return (
          <>
            <mesh position={[0, 2.6, -9.1]}>
              <planeGeometry args={[8.8, 3.2]} />
              <meshPhysicalMaterial color={colors.surface} transparent opacity={0.15 * density} depthWrite={false} roughness={0.3} metalness={0.15} />
            </mesh>
          </>
        );
      default:
        return null;
    }
  }, [colors, density]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    pulseRefs.current.forEach((mesh, idx) => {
      const mat = mesh.material as THREE.MeshPhysicalMaterial;
      mat.opacity = (0.1 + (0.05 + idx * 0.015) * (1 + Math.sin(t * accents[idx].speed))) * density;
    });
    ringRefs.current.forEach((mesh, idx) => {
      mesh.rotation.z = t * (0.05 + idx * 0.015);
      mesh.position.y = 3.2 + idx * 0.42 + Math.sin(t * (0.7 + idx * 0.22)) * 0.08;
    });
  });

  return (
    <group>
      {/* Sky dome shell */}
      <mesh position={[0, 2.7, -4.6]} rotation={[0, Math.PI, 0]}>
        <cylinderGeometry args={[13.8, 14.8, 6.8, 72, 1, true, 0.52, Math.PI - 1.04]} />
        <meshPhysicalMaterial color={colors.skyBottom} transparent opacity={0.22 * density} side={THREE.BackSide} depthWrite={false} roughness={0.8} />
      </mesh>

      {/* Far backdrop */}
      <mesh position={[0, 4.8, -13.5]}>
        <planeGeometry args={[30, 12]} />
        <meshPhysicalMaterial color={colors.skyTop} transparent opacity={0.35 * density} depthWrite={false} />
      </mesh>

      <mesh position={[0, 1.3, -12.5]}>
        <planeGeometry args={[26, 7]} />
        <meshPhysicalMaterial color={colors.skyBottom} transparent opacity={0.55 * density} depthWrite={false} />
      </mesh>

      {/* Ceiling glow wash */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 3.95, -2]}>
        <planeGeometry args={[22, 18]} />
        <meshPhysicalMaterial color={colors.glowSoft} emissive={colors.glowSoft} emissiveIntensity={0.1} transparent opacity={0.1 * density} depthWrite={false} />
      </mesh>

      {/* Floating halo rings – with Float for gentle motion */}
      <Float speed={0.4} rotationIntensity={0.015} floatIntensity={0.03}>
        {[0, 1, 2].map((idx) => (
          <mesh
            key={`halo-${idx}`}
            ref={(node) => {
              if (node) ringRefs.current[idx] = node;
            }}
            rotation={[-Math.PI / 2, 0, 0]}
            position={[0, 3.2 + idx * 0.42, -2.4]}
            scale={[1 + idx * 0.12, 1, 1 + idx * 0.12]}
          >
            <torusGeometry args={[3.2 + idx * 0.48, 0.035, 24, 120]} />
            <meshPhysicalMaterial
              color={idx === 1 ? colors.highlight : colors.trim}
              emissive={idx === 1 ? colors.highlight : colors.trim}
              emissiveIntensity={0.25}
              transparent
              opacity={(0.14 - idx * 0.02) * density}
              depthWrite={false}
              roughness={0.1}
              metalness={0.7}
              clearcoat={0.9}
            />
          </mesh>
        ))}
      </Float>

      {/* Side sails – volumetric light shafts */}
      {[-1, 1].map((side) => (
        <group key={`sail-${side}`} position={[side * 7.4, 2.55, -6.6]} rotation={[0.18, side * 0.44, side * 0.16]}>
          <mesh>
            <planeGeometry args={[2.6, 5.8]} />
            <meshPhysicalMaterial color={colors.mist} emissive={colors.mist} emissiveIntensity={0.06} transparent opacity={0.08 * density} depthWrite={false} />
          </mesh>
          <mesh position={[0, 0, 0.06]}>
            <planeGeometry args={[0.08, 5.2]} />
            <meshPhysicalMaterial color={colors.highlight} emissive={colors.highlight} emissiveIntensity={0.2} transparent opacity={0.16 * density} depthWrite={false} />
          </mesh>
        </group>
      ))}

      {/* Floor accent rings */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, -2]}>
        <ringGeometry args={[1.6, 6.8, 64]} />
        <meshPhysicalMaterial color={colors.trim} emissive={colors.trim} emissiveIntensity={0.08} transparent opacity={0.1 * density} depthWrite={false} roughness={0.2} metalness={0.4} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.016, -2]} scale={[colors.archCurve, 1, colors.archCurve]}>
        <ringGeometry args={[0.9, 1.2, 48]} />
        <meshPhysicalMaterial color={colors.accentStrong} emissive={colors.accentStrong} emissiveIntensity={0.15} transparent opacity={colors.bannerOpacity * density} depthWrite={false} roughness={0.15} metalness={0.5} />
      </mesh>

      {motifElements}

      {/* Ambient pulse beacons */}
      {accents.map((accent, idx) => (
        <mesh
          key={idx}
          ref={(node) => {
            if (node) pulseRefs.current[idx] = node;
          }}
          position={accent.position}
          scale={accent.scale}
        >
          <capsuleGeometry args={[0.5, 0.5, 4, 8]} />
          <meshPhysicalMaterial color={colors.accent} emissive={colors.accent} emissiveIntensity={0.2} transparent opacity={0.14 * density} depthWrite={false} roughness={0.1} />
        </mesh>
      ))}
    </group>
  );
}