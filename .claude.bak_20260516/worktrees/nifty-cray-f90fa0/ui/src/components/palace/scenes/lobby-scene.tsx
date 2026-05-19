"use client";

import { useRef, useState, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Sparkles, Float, MeshReflectorMaterial, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import type { WingInfo } from "@/lib/api/palace";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceMaterials, usePalaceColors } from "@/lib/palace/theme-materials";

// ── Pulsing lobby orb ────────────────────────────────────────────────────

function LobbyOrb() {
  const colors = usePalaceColors();
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (meshRef.current) {
      const scale = 1 + Math.sin(t * 0.8) * 0.08;
      meshRef.current.scale.setScalar(scale);
      meshRef.current.rotation.y = t * 0.15;
      meshRef.current.rotation.x = Math.sin(t * 0.3) * 0.1;
      const mat = meshRef.current.material as THREE.MeshPhysicalMaterial;
      mat.emissiveIntensity = 0.6 + Math.sin(t * 1.2) * 0.2;
    }
    if (glowRef.current) {
      const glowScale = 1.8 + Math.sin(t * 0.6) * 0.3;
      glowRef.current.scale.setScalar(glowScale);
      const mat = glowRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.08 + Math.sin(t * 0.9) * 0.04;
    }
  });

  return (
    <Float speed={0.5} rotationIntensity={0.02} floatIntensity={0.15} floatingRange={[-0.05, 0.05]}>
      <group position={[0, 1.8, -0.6]}>
        {/* Core orb – icosahedron for faceted gem look */}
        <mesh ref={meshRef} castShadow>
          <icosahedronGeometry args={[0.28, 2]} />
          <meshPhysicalMaterial
            color={colors.accent}
            emissive={colors.accentStrong}
            emissiveIntensity={0.6}
            roughness={0.05}
            metalness={0.1}
            clearcoat={1}
            clearcoatRoughness={0.05}
            transmission={0.4}
            thickness={1.2}
            ior={2.0}
            transparent
            opacity={0.85}
          />
        </mesh>
        {/* Outer glow sphere */}
        <mesh ref={glowRef}>
          <sphereGeometry args={[0.28, 32, 32]} />
          <meshBasicMaterial
            color={colors.accent}
            transparent
            opacity={0.08}
            depthWrite={false}
          />
        </mesh>
      </group>
    </Float>
  );
}

// ── Archway geometry (procedural) ─────────────────────────────────────────

function Archway({
  position,
  label,
  hallCount,
  onClick,
}: {
  position: [number, number, number];
  label: string;
  hallCount: number;
  onClick: () => void;
}) {
  const { accent, wall, colors } = usePalaceMaterials();
  const [hovered, setHovered] = useState(false);
  const glowRef = useRef<THREE.Mesh>(null);
  const portalRef = useRef<THREE.Mesh>(null);
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state, delta) => {
    if (groupRef.current) {
      groupRef.current.position.set(position[0], position[1] + Math.sin(state.clock.elapsedTime * 0.9 + position[0]) * 0.03, position[2]);
    }
    if (glowRef.current) {
      const target = hovered ? 0.6 : 0.0;
      const mat = glowRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity += (target - mat.emissiveIntensity) * delta * 6;
    }
    if (portalRef.current) {
      const mat = portalRef.current.material as THREE.MeshPhysicalMaterial;
      const target = hovered ? 0.72 : 0.4;
      mat.emissiveIntensity += (target - mat.emissiveIntensity) * delta * 4;
      mat.opacity += ((hovered ? 0.82 : 0.62) - mat.opacity) * delta * 4;
    }
  });

  // Human-readable label
  const displayLabel = label.replace(/^wing_/, "").replace(/_/g, " ");

  return (
    <group ref={groupRef} position={position}>
      {/* Base pedestal – rounded for premium feel */}
      <mesh position={[0, 0.06, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[1.05, 1.05, 0.12, 48]} />
        <meshPhysicalMaterial color={colors.floorEdge} roughness={0.25} metalness={0.5} clearcoat={0.8} clearcoatRoughness={0.2} />
      </mesh>

      {/* Frame back panel */}
      <RoundedBox args={[1.68, 2.28, 0.24]} radius={0.06} smoothness={4} position={[0, 1.08, -0.16]} castShadow receiveShadow material={wall} />

      {/* Pillars – cylindrical for architectural feel */}
      <mesh position={[-0.66, 1, 0]} castShadow material={accent}>
        <cylinderGeometry args={[0.1, 0.12, 2.12, 20]} />
      </mesh>
      <mesh position={[0.66, 1, 0]} castShadow material={accent}>
        <cylinderGeometry args={[0.1, 0.12, 2.12, 20]} />
      </mesh>

      {/* Lintel with profile */}
      <RoundedBox args={[1.5, 0.2, 0.36]} radius={0.04} smoothness={4} position={[0, 2.12, 0]} castShadow material={accent} />

      {/* Arch crown */}
      <mesh position={[0, 2.1, 0.12]}>
        <torusGeometry args={[0.66, 0.06, 20, 64, Math.PI]} />
        <meshPhysicalMaterial color={colors.highlight} emissive={colors.accentStrong} emissiveIntensity={0.35} roughness={0.15} metalness={0.7} clearcoat={1} clearcoatRoughness={0.1} />
      </mesh>

      {/* Pilaster side accents */}
      {[-1, 1].map((side) => (
        <mesh key={side} position={[side * 0.9, 1.2, -0.08]} castShadow>
          <cylinderGeometry args={[0.04, 0.04, 2.36, 12]} />
          <meshPhysicalMaterial color={colors.highlight} emissive={colors.accentStrong} emissiveIntensity={0.22} roughness={0.2} metalness={0.6} clearcoat={0.9} />
        </mesh>
      ))}

      {/* Portal surface (clickable) – glassy transmission */}
      <mesh
        ref={portalRef}
        position={[0, 1, 0]}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
      >
        <planeGeometry args={[1.05, 2]} />
        <meshPhysicalMaterial
          color={colors.shadow}
          emissive={colors.accent}
          emissiveIntensity={0.4}
          roughness={0.15}
          metalness={0.1}
          transparent
          opacity={0.62}
          transmission={0.3}
          thickness={0.5}
          clearcoat={1}
          clearcoatRoughness={0.1}
        />
      </mesh>

      {/* Glow frame on hover */}
      <mesh ref={glowRef} position={[0, 1, 0.01]}>
        <planeGeometry args={[1.48, 2.32]} />
        <meshStandardMaterial
          color={colors.accent}
          emissive={colors.accent}
          emissiveIntensity={0}
          transparent
          opacity={0.15}
        />
      </mesh>

      {/* Threshold strip */}
      <RoundedBox args={[1.24, 0.08, 0.28]} radius={0.02} smoothness={4} position={[0, 0.06, 0.09]} castShadow>
        <meshPhysicalMaterial color={colors.floorEdge} emissive={colors.accentStrong} emissiveIntensity={0.15} roughness={0.2} metalness={0.5} clearcoat={0.8} />
      </RoundedBox>

      {/* Wing label */}
      <Float speed={1.2} rotationIntensity={0} floatIntensity={0.15} floatingRange={[-0.02, 0.02]}>
        <Text
          position={[0, 2.4, 0]}
          fontSize={0.18}
          color={colors.text}
          anchorX="center"
          anchorY="middle"
          maxWidth={1.5}
        >
          {displayLabel}
        </Text>
      </Float>

      {/* Hall count badge */}
      <Text
        position={[0, 0.15, 0.05]}
        fontSize={0.1}
        color={colors.muted}
        anchorX="center"
        anchorY="middle"
      >
        {hallCount} {hallCount === 1 ? "hall" : "halls"}
      </Text>
    </group>
  );
}

// ── Lobby atrium ──────────────────────────────────────────────────────────

export function LobbyScene({ wings }: { wings: WingInfo[] }) {
  const { wall, floor, colors } = usePalaceMaterials();
  const navigateTo = usePalaceStore((s) => s.navigateTo);
  const palaceColors = usePalaceColors();

  // Arrange archways in a semicircle facing the camera
  const archPositions = useMemo(() => {
    const count = wings.length;
    if (count === 0) return [];
    const radius = Math.max(3, count * 1.2);
    const arcSpan = Math.min(Math.PI * 0.7, count * 0.5);
    const startAngle = Math.PI / 2 - arcSpan / 2;

    return wings.map((_, i) => {
      const angle = startAngle + (count > 1 ? (arcSpan * i) / (count - 1) : arcSpan / 2);
      const x = Math.cos(angle) * radius;
      const z = -Math.sin(angle) * radius;
      return [x, 0, z] as [number, number, number];
    });
  }, [wings]);

  return (
    <group>
      {/* Reflective floor – MeshReflectorMaterial gives the premium polished look */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[20, 20]} />
        <MeshReflectorMaterial
          mirror={0.55}
          blur={[400, 150]}
          resolution={2048}
          mixBlur={0.75}
          mixStrength={0.75}
          depthScale={1.2}
          minDepthThreshold={0.4}
          maxDepthThreshold={1.4}
          color={palaceColors.panel}
          metalness={0.4}
          roughness={0.32}
        />
      </mesh>

      {/* Central floor inlay – glowing ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, -0.6]}>
        <ringGeometry args={[1.4, 2.9, 64]} />
        <meshPhysicalMaterial
          color={palaceColors.accent}
          emissive={palaceColors.accent}
          emissiveIntensity={0.3}
          transparent
          opacity={0.25}
          depthWrite={false}
          roughness={0.15}
          metalness={0.6}
          clearcoat={1}
        />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.011, -0.6]}>
        <ringGeometry args={[3.15, 3.55, 64]} />
        <meshPhysicalMaterial
          color={palaceColors.trim ?? palaceColors.accentStrong}
          emissive={palaceColors.trim ?? palaceColors.accentStrong}
          emissiveIntensity={0.15}
          transparent
          opacity={0.18}
          depthWrite={false}
          roughness={0.2}
          metalness={0.5}
        />
      </mesh>

      {/* Back wall (subtle, fades into fog) */}
      <mesh position={[0, 3, -8]} material={wall} receiveShadow>
        <planeGeometry args={[20, 6]} />
      </mesh>

      {/* Architectural columns in a circle – cylindrical */}
      {Array.from({ length: 9 }).map((_, i) => {
        const angle = (i / 9) * Math.PI * 2;
        const x = Math.cos(angle) * 4.8;
        const z = -0.6 + Math.sin(angle) * 4.8;
        return (
          <mesh key={`rib-${i}`} position={[x, 2.2, z]} castShadow>
            <cylinderGeometry args={[0.06, 0.08, 3.7, 16]} />
            <meshPhysicalMaterial color={palaceColors.trim} emissive={palaceColors.accent} emissiveIntensity={0.1} roughness={0.25} metalness={0.6} clearcoat={0.7} clearcoatRoughness={0.2} />
          </mesh>
        );
      })}

      {/* Ceiling */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 4, 0]} material={wall} receiveShadow>
        <planeGeometry args={[20, 20]} />
      </mesh>

      {/* Canopy glow – emissive dome light */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 3.96, -0.5]}>
        <circleGeometry args={[4.6, 64]} />
        <meshPhysicalMaterial
          color={palaceColors.glowSoft ?? palaceColors.accent}
          emissive={palaceColors.glowSoft ?? palaceColors.accent}
          emissiveIntensity={0.25}
          transparent
          opacity={0.12}
          depthWrite={false}
        />
      </mesh>

      {/* Central chandelier ring */}
      <Float speed={0.6} rotationIntensity={0.02} floatIntensity={0.05}>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 2.72, -0.5]}>
          <torusGeometry args={[3.9, 0.08, 24, 96]} />
          <meshPhysicalMaterial color={palaceColors.highlight} emissive={palaceColors.accentStrong} emissiveIntensity={0.4} roughness={0.1} metalness={0.8} clearcoat={1} clearcoatRoughness={0.05} />
        </mesh>
      </Float>

      {/* Pulsing focal orb */}
      <LobbyOrb />

      {Array.from({ length: 6 }).map((_, i) => {
        const angle = (i / 6) * Math.PI * 2;
        const x = Math.cos(angle) * 2.6;
        const z = -0.5 + Math.sin(angle) * 2.6;
        return (
          <mesh key={`beam-${i}`} position={[x, 2.36, z]} castShadow>
            <cylinderGeometry args={[0.04, 0.06, 1.9, 12]} />
            <meshPhysicalMaterial color={palaceColors.highlight} emissive={palaceColors.accentStrong} emissiveIntensity={0.2} roughness={0.15} metalness={0.7} clearcoat={0.9} />
          </mesh>
        );
      })}

      {/* Archways */}
      {wings.map((w, i) => (
        <Archway
          key={w.name}
          position={archPositions[i] || [i * 2.5 - (wings.length * 1.25), 0, -3]}
          label={w.name}
          hallCount={w.halls.length}
          onClick={() => navigateTo({ level: "wing", wing: w.name })}
        />
      ))}

      {/* Ambient sparkles */}
      <Sparkles
        count={Math.max(20, palaceColors.particleCount)}
        size={1.5}
        scale={[12, 4, 12]}
        position={[0, 2, 0]}
        speed={0.3}
        color={palaceColors.accent}
        opacity={0.3}
      />

      {/* Empty state */}
      {wings.length === 0 && (
        <Text
          position={[0, 1.5, -2]}
          fontSize={0.25}
          color={colors.muted}
          anchorX="center"
          anchorY="middle"
          maxWidth={4}
        >
          The palace is empty.{"\n"}Memories will create rooms as they are stored.
        </Text>
      )}
    </group>
  );
}
