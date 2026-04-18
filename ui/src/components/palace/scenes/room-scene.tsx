"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Float, MeshReflectorMaterial, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceMaterials, usePalaceColors } from "@/lib/palace/theme-materials";
import { DrawerMesh } from "./drawer-mesh";

export function RoomScene() {
  const { wall, floor, colors } = usePalaceMaterials();
  const location = usePalaceStore((s) => s.location);
  const roomMemories = usePalaceStore((s) => s.roomMemories);
  const roomLoading = usePalaceStore((s) => s.roomLoading);
  const loadRoomMemories = usePalaceStore((s) => s.loadRoomMemories);
  const adminViewingOwner = usePalaceStore((s) => s.adminViewingOwner);
  const palaceColors = usePalaceColors();
  const haloRef = useRef<THREE.Mesh>(null);

  // Load memories when room changes
  const prevKey = useRef("");
  const roomKey = `${location.wing}|${location.hall}|${location.room}`;
  useEffect(() => {
    if (roomKey === prevKey.current || !location.wing || !location.hall || !location.room) {
      return;
    }

    prevKey.current = roomKey;
    loadRoomMemories(
      location.wing,
      location.hall,
      location.room,
      adminViewingOwner ?? undefined,
    );
  }, [
    adminViewingOwner,
    loadRoomMemories,
    location.hall,
    location.room,
    location.wing,
    roomKey,
  ]);

  const displayRoom = (location.room || "Unknown").replace(/_/g, " ");
  const displayHall = (location.hall || "").replace(/^hall_/, "").replace(/_/g, " ");

  // Arrange drawers in a grid along walls
  const drawerLayout = useMemo(() => {
    const items = roomMemories;
    const positions: { pos: [number, number, number]; idx: number }[] = [];

    // Layout: 2 rows along left wall, 2 rows along right wall, 2 rows along back wall
    const walls = [
      { startX: -3.3, startZ: -4, dirX: 0, dirZ: 1, rotY: Math.PI / 2 }, // left
      { startX: 3.3, startZ: -4, dirX: 0, dirZ: 1, rotY: -Math.PI / 2 }, // right
      { startX: -2.5, startZ: -4.3, dirX: 1, dirZ: 0, rotY: 0 },        // back
    ];

    let idx = 0;
    const COLS_PER_WALL = 6;
    const ROWS = 3;
    const SPACING_X = 0.85;
    const SPACING_Y = 0.7;

    for (const wall of walls) {
      for (let row = 0; row < ROWS && idx < items.length; row++) {
        for (let col = 0; col < COLS_PER_WALL && idx < items.length; col++) {
          const x = wall.startX + wall.dirX * col * SPACING_X;
          const y = 0.5 + row * SPACING_Y;
          const z = wall.startZ + wall.dirZ * col * SPACING_X;
          positions.push({ pos: [x, y, z], idx });
          idx++;
        }
      }
    }
    return positions;
  }, [roomMemories]);

  useFrame((state, delta) => {
    if (haloRef.current) {
      const mat = haloRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity += ((0.08 + (1 + Math.sin(state.clock.elapsedTime * 1.1)) * 0.02) - mat.opacity) * delta * 4;
    }
  });

  return (
    <group>
      {/* Reflective floor – most important visual upgrade */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[8, 10]} />
        <MeshReflectorMaterial
          mirror={0.6}
          blur={[400, 150]}
          resolution={2048}
          mixBlur={0.7}
          mixStrength={0.75}
          depthScale={1.2}
          minDepthThreshold={0.4}
          maxDepthThreshold={1.4}
          color={palaceColors.panel}
          metalness={0.45}
          roughness={0.28}
        />
      </mesh>

      {/* Walls – with shadow receiving and physical treatment */}
      <mesh position={[-3.5, 2, -2]} material={wall} receiveShadow castShadow>
        <boxGeometry args={[0.15, 4, 8]} />
      </mesh>
      <mesh position={[3.5, 2, -2]} material={wall} receiveShadow castShadow>
        <boxGeometry args={[0.15, 4, 8]} />
      </mesh>
      <mesh position={[0, 2, -4.5]} material={wall} receiveShadow>
        <planeGeometry args={[7, 4]} />
      </mesh>

      {/* Back wall accent panels – glassy insets */}
      {[-2.2, 0, 2.2].map((x, idx) => (
        <RoundedBox key={`back-panel-${x}`} args={[1.48, 3.25, 0.08]} radius={0.04} smoothness={4} position={[x, 1.95, -4.42]} castShadow>
          <meshPhysicalMaterial
            color={idx === 1 ? palaceColors.shadow : palaceColors.surface}
            roughness={0.18}
            metalness={0.25}
            clearcoat={0.9}
            clearcoatRoughness={0.12}
            emissive={palaceColors.accent}
            emissiveIntensity={idx === 1 ? 0.12 : 0.06}
            transparent
            opacity={0.6}
            transmission={idx === 1 ? 0.15 : 0.08}
            thickness={0.5}
          />
        </RoundedBox>
      ))}

      {/* Ceiling */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 4, -2]} material={wall} receiveShadow>
        <planeGeometry args={[8, 10]} />
      </mesh>

      {/* Ceiling light bar – emissive strip */}
      <mesh position={[0, 3.82, -2]}>
        <capsuleGeometry args={[0.06, 5.2, 4, 16]} />
        <meshPhysicalMaterial color={palaceColors.glowSoft ?? palaceColors.accent} emissive={palaceColors.glowSoft ?? palaceColors.accent} emissiveIntensity={0.6} roughness={0.1} metalness={0.2} transparent opacity={0.35} />
      </mesh>
      <mesh position={[0, 3.78, -2]}>
        <capsuleGeometry args={[0.04, 1.8, 4, 12]} />
        <meshPhysicalMaterial color={palaceColors.accent} emissive={palaceColors.accent} emissiveIntensity={0.5} transparent opacity={0.25} roughness={0.1} />
      </mesh>

      {/* Title halo – floating backlight */}
      <mesh position={[0, 3.15, -4.42]}>
        <planeGeometry args={[2.6, 1.05]} />
        <meshPhysicalMaterial color={palaceColors.mist ?? palaceColors.accent} emissive={palaceColors.mist ?? palaceColors.accent} emissiveIntensity={0.2} transparent opacity={0.12} depthWrite={false} />
      </mesh>

      {/* Central halo ring – floating with glow */}
      <Float speed={0.8} rotationIntensity={0.02} floatIntensity={0.04}>
        <mesh ref={haloRef} position={[0, 2.36, -1.2]} rotation={[-Math.PI / 2, 0, 0]}>
          <torusGeometry args={[1.15, 0.05, 24, 80]} />
          <meshPhysicalMaterial color={palaceColors.highlight} emissive={palaceColors.highlight} emissiveIntensity={0.5} roughness={0.08} metalness={0.8} clearcoat={1} clearcoatRoughness={0.05} transparent opacity={0.6} depthWrite={false} />
        </mesh>
      </Float>

      {/* Central dais – polished pedestal */}
      <mesh position={[0, 0.34, -1.2]} castShadow>
        <cylinderGeometry args={[0.82, 0.98, 0.24, 48]} />
        <meshPhysicalMaterial color={palaceColors.floorEdge} emissive={palaceColors.accentStrong} emissiveIntensity={0.12} roughness={0.18} metalness={0.55} clearcoat={0.9} clearcoatRoughness={0.15} />
      </mesh>
      {/* Dais top – glassy crystal surface */}
      <mesh position={[0, 0.56, -1.2]} castShadow>
        <cylinderGeometry args={[0.56, 0.56, 0.08, 48]} />
        <meshPhysicalMaterial
          color={palaceColors.highlight}
          transparent
          opacity={0.55}
          transmission={0.35}
          thickness={0.8}
          roughness={0.05}
          metalness={0.1}
          clearcoat={1}
          clearcoatRoughness={0.05}
          ior={1.5}
        />
      </mesh>

      {/* Side cove accent strips – emissive wall washers */}
      {[-3.18, 3.18].map((x) => (
        <group key={`cove-${x}`} position={[x, 2.05, -2]}>
          <mesh castShadow>
            <capsuleGeometry args={[0.04, 3.1, 4, 12]} />
            <meshPhysicalMaterial color={palaceColors.trim} emissive={palaceColors.accent} emissiveIntensity={0.2} roughness={0.2} metalness={0.5} clearcoat={0.7} />
          </mesh>
          <mesh position={[-Math.sign(x) * 0.04, 0, 0]}>
            <planeGeometry args={[0.42, 7.4]} />
            <meshPhysicalMaterial color={palaceColors.mist} emissive={palaceColors.mist} emissiveIntensity={0.1} transparent opacity={0.1} depthWrite={false} />
          </mesh>
        </group>
      ))}

      {/* Room title on back wall */}
      <Text
        position={[0, 3.3, -4.4]}
        fontSize={0.22}
        color={colors.text}
        anchorX="center"
        anchorY="middle"
      >
        {displayRoom}
      </Text>
      <Text
        position={[0, 3.0, -4.4]}
        fontSize={0.1}
        color={colors.muted}
        anchorX="center"
        anchorY="middle"
      >
        {displayHall} · {roomMemories.length} memories
      </Text>

      {/* Drawers */}
      {drawerLayout.map(({ pos, idx }) => (
        <DrawerMesh
          key={roomMemories[idx].id}
          position={pos}
          memory={roomMemories[idx]}
        />
      ))}

      {/* Perimeter trim – glowing baseboard */}
      <mesh position={[0, 0.42, -4.42]}>
        <capsuleGeometry args={[0.02, 7, 4, 12]} />
        <meshPhysicalMaterial color={palaceColors.trim ?? palaceColors.accentStrong} emissive={palaceColors.trim ?? palaceColors.accentStrong} emissiveIntensity={0.25} transparent opacity={0.3} roughness={0.15} metalness={0.4} />
      </mesh>
      <mesh position={[-3.42, 0.42, -2]}>
        <capsuleGeometry args={[0.02, 8, 4, 12]} />
        <meshPhysicalMaterial color={palaceColors.trim ?? palaceColors.accentStrong} emissive={palaceColors.trim ?? palaceColors.accentStrong} emissiveIntensity={0.2} transparent opacity={0.25} roughness={0.15} metalness={0.4} />
      </mesh>
      <mesh position={[3.42, 0.42, -2]}>
        <capsuleGeometry args={[0.02, 8, 4, 12]} />
        <meshPhysicalMaterial color={palaceColors.trim ?? palaceColors.accentStrong} emissive={palaceColors.trim ?? palaceColors.accentStrong} emissiveIntensity={0.2} transparent opacity={0.25} roughness={0.15} metalness={0.4} />
      </mesh>

      {/* Loading indicator */}
      {roomLoading && (
        <Text
          position={[0, 1.5, -2]}
          fontSize={0.18}
          color={palaceColors.accent}
          anchorX="center"
          anchorY="middle"
        >
          Loading memories…
        </Text>
      )}

      {/* Empty room */}
      {!roomLoading && roomMemories.length === 0 && (
        <group>
          <Text
            position={[0, 1.6, -2]}
            fontSize={0.2}
            color={colors.muted}
            anchorX="center"
            anchorY="middle"
            maxWidth={4}
          >
            This room is empty.
          </Text>
          <Text
            position={[0, 1.2, -2]}
            fontSize={0.12}
            color={colors.muted}
            anchorX="center"
            anchorY="middle"
            maxWidth={4}
          >
            Memories stored in this domain will appear as drawers here.
          </Text>
        </group>
      )}

      {/* Accent floor rug – emissive glow on the reflective floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, -1]}>
        <planeGeometry args={[3, 4]} />
        <meshPhysicalMaterial
          color={palaceColors.accent}
          emissive={palaceColors.accent}
          emissiveIntensity={0.1}
          transparent
          opacity={0.1}
          roughness={0.4}
          metalness={0.15}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.007, -1]}>
        <ringGeometry args={[1.1, 1.9, 64]} />
        <meshPhysicalMaterial color={palaceColors.highlight} emissive={palaceColors.highlight} emissiveIntensity={0.2} transparent opacity={0.18} depthWrite={false} roughness={0.15} metalness={0.5} />
      </mesh>
    </group>
  );
}
