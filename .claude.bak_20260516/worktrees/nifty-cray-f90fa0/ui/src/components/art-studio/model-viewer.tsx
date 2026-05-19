"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF, Grid, Environment } from "@react-three/drei";
import * as THREE from "three";
import { useArtStore, type JointName } from "@/lib/stores/art-store";

// ── Joint marker colors ───────────────────────────────────────────────────

const JOINT_COLORS: Record<string, string> = {
  neck: "#f59e0b",
  left_shoulder: "#3b82f6", right_shoulder: "#3b82f6",
  left_elbow: "#8b5cf6", right_elbow: "#8b5cf6",
  waist: "#ef4444",
  left_hip: "#10b981", right_hip: "#10b981",
  left_knee: "#ec4899", right_knee: "#ec4899",
};

// ── Loaded GLB model with click handler ───────────────────────────────────

function LoadedModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const groupRef = useRef<THREE.Group>(null);
  const { activeJoint, placeJoint } = useArtStore();
  const { raycaster, pointer, camera } = useThree();

  // Center and scale the model on load
  useEffect(() => {
    if (!groupRef.current) return;
    const box = new THREE.Box3().setFromObject(groupRef.current);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = 2 / maxDim; // Normalize to ~2 units
    groupRef.current.scale.setScalar(scale);
    groupRef.current.position.set(
      -center.x * scale,
      -box.min.y * scale, // bottom at y=0
      -center.z * scale,
    );
  }, [scene]);

  const handleClick = useCallback(
    (e: { point: THREE.Vector3; stopPropagation: () => void }) => {
      if (!activeJoint || !e.point) return;
      e.stopPropagation();
      placeJoint({
        name: activeJoint,
        position: [e.point.x, e.point.y, e.point.z],
      });
    },
    [activeJoint, placeJoint],
  );

  return (
    <group ref={groupRef}>
      <primitive
        object={scene}
        onClick={handleClick}
      />
    </group>
  );
}

// ── Joint marker spheres ──────────────────────────────────────────────────

function JointMarkers() {
  const placedJoints = useArtStore((s) => s.placedJoints);

  return (
    <>
      {placedJoints.map((j) => (
        <mesh key={j.name} position={j.position}>
          <sphereGeometry args={[0.04, 16, 16]} />
          <meshStandardMaterial
            color={JOINT_COLORS[j.name] || "#ffffff"}
            emissive={JOINT_COLORS[j.name] || "#ffffff"}
            emissiveIntensity={0.5}
          />
        </mesh>
      ))}
    </>
  );
}

// ── Main viewer component ─────────────────────────────────────────────────

interface ModelViewerProps {
  url: string;
}

export function ModelViewer({ url }: ModelViewerProps) {
  const activeJoint = useArtStore((s) => s.activeJoint);

  return (
    <div className="w-full h-full relative">
      <Canvas
        camera={{ position: [0, 1.5, 3], fov: 45 }}
        style={{ cursor: activeJoint ? "crosshair" : "grab" }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 5, 5]} intensity={0.8} />
        <directionalLight position={[-3, 3, -3]} intensity={0.3} />

        <LoadedModel url={url} />
        <JointMarkers />

        <Grid
          args={[10, 10]}
          position={[0, 0, 0]}
          cellSize={0.2}
          cellColor="#333"
          sectionSize={1}
          sectionColor="#555"
          fadeDistance={8}
          infiniteGrid
        />

        <OrbitControls
          makeDefault
          enablePan
          minDistance={0.5}
          maxDistance={10}
        />
      </Canvas>

      {activeJoint && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-violet-600/90 text-white text-xs font-medium px-3 py-1.5 rounded-full backdrop-blur-sm">
          Click on the model to place: {activeJoint.replace(/_/g, " ")}
        </div>
      )}
    </div>
  );
}
