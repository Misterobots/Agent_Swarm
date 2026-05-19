"use client";

import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Sparkles, Float, MeshReflectorMaterial, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import type { HallInfo } from "@/lib/api/palace";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceMaterials, usePalaceColors } from "@/lib/palace/theme-materials";

// ── Door component ────────────────────────────────────────────────────────

function Door({
  position,
  label,
  roomCount,
  side,
  onClick,
}: {
  position: [number, number, number];
  label: string;
  roomCount: number;
  side: "left" | "right";
  onClick: () => void;
}) {
  const { accent, wall, colors } = usePalaceMaterials();
  const [hovered, setHovered] = useState(false);
  const panelRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);

  const displayLabel = label.replace(/^hall_/, "").replace(/_/g, " ");

  // Doors face inward from the corridor walls
  const rotY = side === "left" ? Math.PI / 2 : -Math.PI / 2;

  useFrame((state, delta) => {
    if (panelRef.current) {
      const mat = panelRef.current.material as THREE.MeshPhysicalMaterial;
      mat.emissiveIntensity += (((hovered ? 0.75 : 0.3) + Math.sin(state.clock.elapsedTime * 1.4) * 0.04) - mat.emissiveIntensity) * delta * 4;
      mat.opacity += ((hovered ? 0.88 : 0.72) - mat.opacity) * delta * 4;
    }
    if (glowRef.current) {
      const mat = glowRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity += (((hovered ? 0.22 : 0.08)) - mat.opacity) * delta * 5;
    }
  });

  return (
    <group position={position} rotation={[0, rotY, 0]}>
      {/* Door frame back */}
      <RoundedBox args={[1.16, 2.16, 0.2]} radius={0.04} smoothness={4} position={[0, 0.94, -0.12]} castShadow receiveShadow material={wall} />

      {/* Frame pillars – cylinders */}
      <mesh position={[-0.48, 0.95, 0]} castShadow material={accent}>
        <cylinderGeometry args={[0.06, 0.07, 1.96, 16]} />
      </mesh>
      <mesh position={[0.48, 0.95, 0]} castShadow material={accent}>
        <cylinderGeometry args={[0.06, 0.07, 1.96, 16]} />
      </mesh>

      {/* Lintel */}
      <RoundedBox args={[1.08, 0.12, 0.16]} radius={0.03} smoothness={4} position={[0, 1.98, 0]} castShadow material={accent} />

      {/* Arch crown */}
      <mesh position={[0, 2.04, 0.09]}>
        <torusGeometry args={[0.52, 0.035, 20, 48, Math.PI]} />
        <meshPhysicalMaterial color={colors.highlight} emissive={colors.accentStrong} emissiveIntensity={0.25} roughness={0.1} metalness={0.75} clearcoat={1} clearcoatRoughness={0.08} />
      </mesh>

      {/* Door panel (clickable) – transmission glass effect */}
      <mesh
        ref={panelRef}
        position={[0, 0.95, 0]}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
      >
        <planeGeometry args={[0.82, 1.82]} />
        <meshPhysicalMaterial
          color={hovered ? colors.accent : colors.shadow}
          emissive={colors.accent}
          emissiveIntensity={0.3}
          roughness={0.12}
          metalness={0.15}
          clearcoat={0.9}
          clearcoatRoughness={0.1}
          transparent
          opacity={0.72}
          transmission={0.25}
          thickness={0.3}
        />
      </mesh>

      <mesh ref={glowRef} position={[0, 0.95, 0.03]}>
        <planeGeometry args={[0.98, 1.98]} />
        <meshBasicMaterial color={colors.highlight} transparent opacity={0.08} depthWrite={false} />
      </mesh>

      {/* Threshold */}
      <RoundedBox args={[0.96, 0.05, 0.18]} radius={0.015} smoothness={4} position={[0, 0.06, 0.06]} castShadow>
        <meshPhysicalMaterial color={colors.floorEdge} emissive={colors.accentStrong} emissiveIntensity={0.12} roughness={0.2} metalness={0.5} clearcoat={0.7} />
      </RoundedBox>

      {/* Hall name */}
      <Float speed={1.2} rotationIntensity={0} floatIntensity={0.1} floatingRange={[-0.01, 0.01]}>
        <Text
          position={[0, 2.2, 0]}
          fontSize={0.13}
          color={colors.text}
          anchorX="center"
          anchorY="middle"
          maxWidth={1.2}
        >
          {displayLabel}
        </Text>
      </Float>

      {/* Room count */}
      <Text
        position={[0, 0.12, 0.02]}
        fontSize={0.08}
        color={colors.muted}
        anchorX="center"
        anchorY="middle"
      >
        {roomCount} {roomCount === 1 ? "room" : "rooms"}
      </Text>

      {/* Door handle */}
      <mesh position={[0.3, 0.95, 0.05]}>
        <sphereGeometry args={[0.03, 8, 8]} />
        <meshStandardMaterial
          color={colors.accent}
          metalness={0.6}
          roughness={0.3}
        />
      </mesh>
    </group>
  );
}

// ── Wing corridor ─────────────────────────────────────────────────────────

export function WingScene({
  wingName,
  halls,
}: {
  wingName: string;
  halls: HallInfo[];
}) {
  const { wall, floor, colors } = usePalaceMaterials();
  const navigateTo = usePalaceStore((s) => s.navigateTo);
  const palaceColors = usePalaceColors();

  const displayWing = wingName.replace(/^wing_/, "").replace(/_/g, " ");

  // If a hall has exactly one room, skip straight to room level
  const handleHallClick = (hall: HallInfo) => {
    if (hall.rooms.length === 1) {
      navigateTo({
        level: "room",
        wing: wingName,
        hall: hall.name,
        room: hall.rooms[0].name,
      });
    } else {
      // For multi-room halls, navigate to room selection
      // For now, enter first room (room picker can be a future enhancement)
      navigateTo({
        level: "room",
        wing: wingName,
        hall: hall.name,
        room: hall.rooms[0]?.name ?? "general",
      });
    }
  };

  return (
    <group>
      {/* Reflective floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[6, 20]} />
        <MeshReflectorMaterial
          mirror={0.55}
          blur={[350, 120]}
          resolution={2048}
          mixBlur={0.8}
          mixStrength={0.65}
          depthScale={1}
          minDepthThreshold={0.4}
          maxDepthThreshold={1.4}
          color={palaceColors.panel}
          metalness={0.35}
          roughness={0.35}
        />
      </mesh>

      {/* Left wall */}
      <mesh position={[-3, 2, -4]} material={wall} receiveShadow castShadow>
        <boxGeometry args={[0.15, 4, 14]} />
      </mesh>

      {/* Right wall */}
      <mesh position={[3, 2, -4]} material={wall} receiveShadow castShadow>
        <boxGeometry args={[0.15, 4, 14]} />
      </mesh>

      {/* Ceiling */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 4, -4]} material={wall} receiveShadow>
        <planeGeometry args={[6, 14]} />
      </mesh>

      {/* Ceiling track – emissive glow strip */}
      <mesh position={[0, 3.85, -4]}>
        <boxGeometry args={[0.5, 0.04, 14]} />
        <meshPhysicalMaterial color={palaceColors.glowSoft ?? palaceColors.accent} emissive={palaceColors.glowSoft ?? palaceColors.accent} emissiveIntensity={0.4} transparent opacity={0.25} depthWrite={false} />
      </mesh>

      {/* Structural arch ribs + wall sconces */}
      {Array.from({ length: 5 }).map((_, i) => {
        const z = 1.6 - i * 3.05;
        return (
          <group key={`rib-${z}`} position={[0, 0, z]}>
            {/* Left column */}
            <mesh position={[-2.78, 2.04, 0]} castShadow>
              <cylinderGeometry args={[0.04, 0.05, 2.9, 12]} />
              <meshPhysicalMaterial color={palaceColors.trim} emissive={palaceColors.accent} emissiveIntensity={0.1} roughness={0.2} metalness={0.6} clearcoat={0.8} />
            </mesh>
            {/* Right column */}
            <mesh position={[2.78, 2.04, 0]} castShadow>
              <cylinderGeometry args={[0.04, 0.05, 2.9, 12]} />
              <meshPhysicalMaterial color={palaceColors.trim} emissive={palaceColors.accent} emissiveIntensity={0.1} roughness={0.2} metalness={0.6} clearcoat={0.8} />
            </mesh>
            {/* Crown beam */}
            <mesh position={[0, 3.45, 0]}>
              <torusGeometry args={[2.76, 0.04, 12, 48, Math.PI]} />
              <meshPhysicalMaterial color={palaceColors.highlight} emissive={palaceColors.accentStrong} emissiveIntensity={0.2} roughness={0.1} metalness={0.7} clearcoat={0.9} />
            </mesh>
            {/* Wall sconces — emissive triangles between arches */}
            {[-2.65, 2.65].map((x) => (
              <group key={`sconce-${x}-${z}`} position={[x, 2.6, 0]}>
                <mesh>
                  <sphereGeometry args={[0.06, 16, 16]} />
                  <meshPhysicalMaterial color={palaceColors.accent} emissive={palaceColors.accent} emissiveIntensity={0.8} roughness={0.05} metalness={0.2} transparent opacity={0.7} />
                </mesh>
                <pointLight
                  position={[0, 0, 0]}
                  intensity={0.15}
                  color={palaceColors.glowSoft ?? palaceColors.accent}
                  distance={3}
                  decay={2}
                />
              </group>
            ))}
          </group>
        );
      })}

      {/* End wall */}
      <mesh position={[0, 2, -11]} material={wall} receiveShadow>
        <planeGeometry args={[6, 4]} />
      </mesh>

      {/* End portal glow – emissive focal point */}
      <mesh position={[0, 2, -10.95]}>
        <planeGeometry args={[2.1, 2.7]} />
        <meshPhysicalMaterial color={palaceColors.accent} emissive={palaceColors.accent} emissiveIntensity={0.45} transparent opacity={0.18} depthWrite={false} />
      </mesh>

      <RoundedBox args={[2.46, 3.05, 0.08]} radius={0.06} smoothness={4} position={[0, 2, -10.88]}>
        <meshPhysicalMaterial color={palaceColors.highlight} emissive={palaceColors.highlight} emissiveIntensity={0.15} transparent opacity={0.12} depthWrite={false} roughness={0.15} metalness={0.5} clearcoat={0.8} />
      </RoundedBox>

      {[-1, 1].map((side) => (
        <mesh key={`wash-${side}`} position={[side * 2.6, 2.25, -4]} rotation={[0, side * 0.16, 0]}>
          <planeGeometry args={[0.65, 12.8]} />
          <meshBasicMaterial color={palaceColors.mist} transparent opacity={0.08} depthWrite={false} />
        </mesh>
      ))}

      {/* Wing name at entrance */}
      <Text
        position={[0, 3.2, 3]}
        fontSize={0.22}
        color={colors.text}
        anchorX="center"
        anchorY="middle"
      >
        {displayWing}
      </Text>

      {/* Doors along corridor */}
      {halls.map((hall, i) => {
        const side = i % 2 === 0 ? "left" : "right" as "left" | "right";
        const xPos = side === "left" ? -2.8 : 2.8;
        const zPos = -1 - Math.floor(i / 2) * 3;
        const totalRooms = hall.rooms.reduce((s, r) => s + r.drawer_count, 0);

        return (
          <Door
            key={hall.name}
            position={[xPos, 0, zPos]}
            label={hall.name}
            roomCount={hall.rooms.length}
            side={side}
            onClick={() => handleHallClick(hall)}
          />
        );
      })}

      {/* Wall guide lights – emissive strips */}
      {Array.from({ length: 4 }).map((_, i) => {
        const z = 1.5 - i * 3.3;
        return (
          <group key={z}>
            <mesh position={[-2.87, 2.4, z]} castShadow>
              <capsuleGeometry args={[0.03, 0.54, 4, 12]} />
              <meshPhysicalMaterial color={palaceColors.accent} emissive={palaceColors.accent} emissiveIntensity={0.6} roughness={0.1} metalness={0.3} />
            </mesh>
            <mesh position={[2.87, 2.4, z]} castShadow>
              <capsuleGeometry args={[0.03, 0.54, 4, 12]} />
              <meshPhysicalMaterial color={palaceColors.accent} emissive={palaceColors.accent} emissiveIntensity={0.6} roughness={0.1} metalness={0.3} />
            </mesh>
          </group>
        );
      })}

      {/* Accent floor strip (carpet runner) – emissive center line */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, -4]}>
        <planeGeometry args={[1.2, 14]} />
        <meshPhysicalMaterial
          color={palaceColors.accent}
          emissive={palaceColors.accent}
          emissiveIntensity={0.08}
          transparent
          opacity={0.15}
          roughness={0.4}
          metalness={0.2}
        />
      </mesh>

      {/* Ambient sparkles */}
      <Sparkles
        count={Math.max(12, Math.round(palaceColors.particleCount * 0.55))}
        size={1}
        scale={[5, 3, 12]}
        position={[0, 2, -4]}
        speed={0.2}
        color={palaceColors.accent}
        opacity={0.25}
      />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, -4]}>
        <planeGeometry args={[0.28, 14]} />
        <meshPhysicalMaterial color={palaceColors.accentStrong} emissive={palaceColors.accentStrong} emissiveIntensity={0.35} transparent opacity={0.25} depthWrite={false} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.011, -4]}>
        <planeGeometry args={[2.2, 14]} />
        <meshBasicMaterial color={palaceColors.floorEdge} transparent opacity={0.09} />
      </mesh>
    </group>
  );
}
