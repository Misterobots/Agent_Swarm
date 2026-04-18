"use client";

import { useRef, useState, useCallback, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Html, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import type { MemoryItem } from "@/lib/api/palace";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceMaterials, usePalaceColors } from "@/lib/palace/theme-materials";

interface DrawerMeshProps {
  position: [number, number, number];
  memory: MemoryItem;
}

const DRAWER_WIDTH = 0.7;
const DRAWER_HEIGHT = 0.55;
const DRAWER_DEPTH = 0.5;
const OPEN_OFFSET = 0.35;

// ── Memory-type visual encoding ────────────────────────────────────────

const TYPE_ICON: Record<string, string> = {
  conversation: "💬",
  code: "⟨⟩",
  error: "⚠",
  decision: "◆",
  task: "☐",
  general: "◎",
};

/** Map domain strings to hue offsets (in degrees) for handle tint */
function domainHue(domain: string | null): number {
  if (!domain) return 0;
  let hash = 0;
  for (let i = 0; i < domain.length; i++) {
    hash = domain.charCodeAt(i) + ((hash << 5) - hash);
  }
  return ((hash % 360) + 360) % 360;
}

/** Compute age factor 0→1 where 0 = just created, 1 = > 30 days old */
function ageFactor(createdAt: string): number {
  const ageMs = Date.now() - new Date(createdAt).getTime();
  const ageDays = ageMs / (1000 * 60 * 60 * 24);
  return Math.min(ageDays / 30, 1);
}

/** Intensity from access count: 0.1 base, grows to 0.6 at 20+ accesses */
function accessIntensity(count: number): number {
  return 0.1 + Math.min(count / 20, 1) * 0.5;
}

export function DrawerMesh({ position, memory }: DrawerMeshProps) {
  const { drawer, drawerHighlight, colors } = usePalaceMaterials();
  const palaceColors = usePalaceColors();
  const selectMemory = usePalaceStore((s) => s.selectMemory);
  const highlightedIds = usePalaceStore((s) => s.highlightedMemoryIds);
  const searchResults = usePalaceStore((s) => s.searchResults);

  const [hovered, setHovered] = useState(false);
  const [peeking, setPeeking] = useState(false);
  const slideRef = useRef(0);
  const groupRef = useRef<THREE.Group>(null);
  const pulseRef = useRef(0);
  const typeGlowRef = useRef<THREE.Mesh>(null);

  const isHighlighted = highlightedIds.has(memory.id);
  const isSearchActive = searchResults !== null && searchResults.length > 0;
  const isDimmed = isSearchActive && !isHighlighted;
  const isActive = hovered || isHighlighted;

  // Compute memory-aware visual properties
  const vis = useMemo(() => {
    const age = ageFactor(memory.created_at);
    const intensity = accessIntensity(memory.access_count);
    const hue = domainHue(memory.domain);
    const icon = TYPE_ICON[memory.memory_type] ?? TYPE_ICON.general;

    // Age → desaturation: newer is vivid, older is faded
    const saturation = 1 - age * 0.4; // 1.0 → 0.6
    const ageOpacity = 1 - age * 0.15; // 1.0 → 0.85

    // Handle color tinted by domain hue
    const handleColor = new THREE.Color();
    handleColor.setHSL(hue / 360, 0.6 * saturation, 0.55);

    return { age, intensity, hue, icon, saturation, ageOpacity, handleColor };
  }, [memory.created_at, memory.access_count, memory.domain, memory.memory_type]);

  const hoverScale = useRef(1);

  // Animate drawer slide + search pulse + type glow + hover scale
  useFrame((state, delta) => {
    const target = peeking ? OPEN_OFFSET : 0;
    slideRef.current += (target - slideRef.current) * delta * 8;
    if (groupRef.current) {
      groupRef.current.position.z = slideRef.current;
      // Hover scale — spring-like pop
      const scaleTarget = hovered ? 1.08 : 1;
      hoverScale.current += (scaleTarget - hoverScale.current) * delta * 12;
      groupRef.current.scale.setScalar(hoverScale.current);
    }

    // Search highlight pulse
    if (isHighlighted) {
      pulseRef.current = 0.3 + Math.sin(state.clock.elapsedTime * 4) * 0.15;
    }

    // Type accent glow animation
    if (typeGlowRef.current) {
      const mat = typeGlowRef.current.material as THREE.MeshPhysicalMaterial;
      const targetEmissive = isActive ? vis.intensity * 1.2 : vis.intensity * 0.5;
      mat.emissiveIntensity += (targetEmissive - mat.emissiveIntensity) * delta * 4;
    }
  });

  const handleClick = useCallback(
    (e: { stopPropagation: () => void }) => {
      e.stopPropagation();
      if (peeking) {
        selectMemory(memory);
      } else {
        setPeeking(true);
      }
    },
    [peeking, memory, selectMemory],
  );

  const handlePointerLeave = useCallback(() => {
    setHovered(false);
    setTimeout(() => setPeeking(false), 800);
  }, []);

  const truncated =
    memory.content.length > 40
      ? memory.content.slice(0, 40) + "…"
      : memory.content;

  return (
    <group position={position}>
      {/* Sliding drawer body */}
      <group ref={groupRef}>
        <RoundedBox
          args={[DRAWER_WIDTH, DRAWER_HEIGHT, DRAWER_DEPTH]}
          radius={0.04}
          smoothness={4}
          onClick={handleClick}
          onPointerEnter={() => setHovered(true)}
          onPointerLeave={handlePointerLeave}
          castShadow
          receiveShadow
        >
          <meshPhysicalMaterial
            color={isActive ? colors.accent : colors.border}
            roughness={isActive ? 0.18 : 0.42}
            metalness={isActive ? 0.44 : 0.3}
            clearcoat={isActive ? 0.65 : 0.35}
            clearcoatRoughness={isActive ? 0.22 : 0.5}
            emissive={isActive ? colors.accentStrong : colors.accent}
            emissiveIntensity={isHighlighted ? pulseRef.current : isActive ? 0.52 : vis.intensity * 0.15}
            transparent={isDimmed}
            opacity={isDimmed ? 0.35 : vis.ageOpacity}
          />
        </RoundedBox>

        {/* Type accent strip — colored bar on left side encodes memory type */}
        <mesh
          ref={typeGlowRef}
          position={[-DRAWER_WIDTH / 2 + 0.02, 0, DRAWER_DEPTH / 2 + 0.005]}
          castShadow
        >
          <planeGeometry args={[0.04, DRAWER_HEIGHT - 0.08]} />
          <meshPhysicalMaterial
            color={`#${vis.handleColor.getHexString()}`}
            emissive={`#${vis.handleColor.getHexString()}`}
            emissiveIntensity={vis.intensity * 0.5}
            roughness={0.1}
            metalness={0.6}
          />
        </mesh>

        {/* Handle – tinted by domain */}
        <mesh position={[0, 0, DRAWER_DEPTH / 2 + 0.02]} castShadow>
          <capsuleGeometry args={[0.025, 0.14, 6, 12]} />
          <meshPhysicalMaterial
            color={`#${vis.handleColor.getHexString()}`}
            metalness={0.85}
            roughness={0.1}
            clearcoat={1}
            clearcoatRoughness={0.05}
            emissive={isActive ? palaceColors.accentStrong : `#${vis.handleColor.getHexString()}`}
            emissiveIntensity={isActive ? 0.3 : 0.05}
          />
        </mesh>

        {/* Type icon (top-right corner) */}
        <Text
          position={[DRAWER_WIDTH / 2 - 0.08, DRAWER_HEIGHT / 2 - 0.08, DRAWER_DEPTH / 2 + 0.01]}
          fontSize={0.06}
          color={`#${vis.handleColor.getHexString()}`}
          anchorX="center"
          anchorY="middle"
        >
          {vis.icon}
        </Text>

        {/* Label on drawer face */}
        <Text
          position={[0, 0.08, DRAWER_DEPTH / 2 + 0.01]}
          fontSize={0.055}
          color={isDimmed ? colors.muted : colors.text}
          anchorX="center"
          anchorY="middle"
          maxWidth={DRAWER_WIDTH - 0.18}
        >
          {truncated}
        </Text>

        {/* Memory type badge */}
        <Text
          position={[0, -0.15, DRAWER_DEPTH / 2 + 0.01]}
          fontSize={0.04}
          color={colors.muted}
          anchorX="center"
          anchorY="middle"
        >
          {memory.memory_type}
        </Text>

        {/* Access frequency indicator — small dots at bottom */}
        {memory.access_count > 0 && (
          <mesh position={[0, -DRAWER_HEIGHT / 2 + 0.04, DRAWER_DEPTH / 2 + 0.005]}>
            <planeGeometry args={[Math.min(memory.access_count / 20, 1) * (DRAWER_WIDTH - 0.16), 0.02]} />
            <meshPhysicalMaterial
              color={palaceColors.accentStrong}
              emissive={palaceColors.accentStrong}
              emissiveIntensity={0.4}
              transparent
              opacity={0.6}
            />
          </mesh>
        )}

        {/* Peek preview when drawer is open */}
        {peeking && (
          <Html
            position={[0, 0.45, 0.1]}
            center
            distanceFactor={4}
            style={{ pointerEvents: "none" }}
          >
            <div
              style={{
                background: `${palaceColors.surface}ee`,
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
                border: `1px solid ${palaceColors.border}40`,
                borderRadius: "10px",
                padding: "10px 14px",
                maxWidth: "230px",
                fontSize: "11px",
                color: palaceColors.text,
                lineHeight: "1.4",
                boxShadow: `0 8px 32px rgba(0,0,0,0.35)`,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 4, color: palaceColors.accent }}>
                {vis.icon} {memory.memory_type} · {memory.domain}
              </div>
              <div>{memory.content.slice(0, 120)}{memory.content.length > 120 ? "…" : ""}</div>
              <div style={{ marginTop: 6, fontSize: "10px", color: palaceColors.muted, display: "flex", justifyContent: "space-between" }}>
                <span>Click again to open</span>
                <span>{memory.access_count}× accessed</span>
              </div>
            </div>
          </Html>
        )}
      </group>

      {/* Drawer cavity (visible when open) */}
      <RoundedBox args={[DRAWER_WIDTH - 0.04, DRAWER_HEIGHT - 0.04, DRAWER_DEPTH]} radius={0.02} smoothness={3}>
        <meshPhysicalMaterial color={colors.bg} roughness={0.6} metalness={0.1} />
      </RoundedBox>
    </group>
  );
}
