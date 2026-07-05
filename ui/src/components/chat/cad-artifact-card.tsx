"use client";

import { Suspense, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Environment } from "@react-three/drei";
import { useLoader } from "@react-three/fiber";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import * as THREE from "three";
import type { CadArtifact } from "@/types/chat";

// ── STL mesh ─────────────────────────────────────────────────────────────────

function STLMesh({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const meshRef = useRef<THREE.Mesh>(null);

  // Center geometry on load
  geometry.computeBoundingBox();
  const box = geometry.boundingBox!;
  const center = new THREE.Vector3();
  box.getCenter(center);
  geometry.translate(-center.x, -center.y, -center.z);

  return (
    <mesh ref={meshRef} geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial
        color="#4f8ef7"
        roughness={0.5}
        metalness={0.15}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

// ── 3D Viewer ─────────────────────────────────────────────────────────────────

function STLViewer({ url }: { url: string }) {
  return (
    <Canvas
      shadows
      camera={{ position: [60, 50, 90], fov: 45 }}
      style={{ background: "#0d0f14", borderRadius: "0 0 8px 8px" }}
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 8, 5]} intensity={1.2} castShadow />
      <directionalLight position={[-4, 2, -4]} intensity={0.4} color="#8ab4f8" />
      <Suspense fallback={null}>
        <STLMesh url={url} />
      </Suspense>
      <Grid
        args={[200, 200]}
        cellSize={10}
        cellThickness={0.5}
        cellColor="#2a2d38"
        sectionSize={50}
        sectionColor="#1e2028"
        fadeDistance={300}
        fadeStrength={1}
        infiniteGrid
      />
      <OrbitControls enableDamping dampingFactor={0.08} makeDefault />
    </Canvas>
  );
}

// ── Source viewer ─────────────────────────────────────────────────────────────

function ScadSource({ source }: { source: string }) {
  return (
    <pre
      className="overflow-auto text-xs leading-relaxed rounded p-3 max-h-64"
      style={{
        background: "var(--chat-surface, #161920)",
        border: "1px solid var(--chat-border, #2a2d38)",
        color: "var(--chat-muted, #9ca3af)",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
        whiteSpace: "pre",
      }}
    >
      {source}
    </pre>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────────

interface CadArtifactCardProps {
  artifact: CadArtifact;
}

export function CadArtifactCard({ artifact }: CadArtifactCardProps) {
  const [showSource, setShowSource] = useState(false);
  const [wireframe, setWireframe] = useState(false);

  const { id, prompt, scad_source, scad_url, stl_url, render_ok, render_error } = artifact;

  return (
    <div
      className="mt-3 rounded-lg overflow-hidden"
      style={{
        border: "1px solid var(--chat-border, #2a2d38)",
        background: "var(--chat-surface, #161920)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{ borderBottom: "1px solid var(--chat-border, #2a2d38)" }}
      >
        <span style={{ fontSize: 16 }}>📐</span>
        <span className="text-sm font-semibold flex-1 truncate" style={{ color: "var(--chat-text, #e2e6f0)" }}>
          CAD Model
        </span>
        {render_ok ? (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#14532d", color: "#34d399" }}>
            STL ready
          </span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#450a0a", color: "#f87171" }}>
            SCAD only
          </span>
        )}
      </div>

      {/* 3D viewer */}
      {stl_url ? (
        <div style={{ height: 320 }}>
          <STLViewer url={stl_url} />
        </div>
      ) : (
        <div
          className="flex flex-col items-center justify-center gap-2 py-8 text-sm"
          style={{ color: "var(--chat-muted, #6b7280)" }}
        >
          <span style={{ fontSize: 32 }}>⚠️</span>
          <span>STL render unavailable</span>
          {render_error && (
            <span
              className="text-xs px-3 py-1 rounded max-w-xs text-center"
              style={{ background: "#1c0a0a", color: "#f87171" }}
            >
              {render_error}
            </span>
          )}
          <span className="text-xs" style={{ color: "var(--chat-muted, #6b7280)" }}>
            Source code available below
          </span>
        </div>
      )}

      {/* Action row */}
      <div
        className="flex items-center gap-2 px-3 py-2 flex-wrap"
        style={{ borderTop: "1px solid var(--chat-border, #2a2d38)" }}
      >
        {stl_url && (
          <a
            href={stl_url}
            download
            className="text-xs px-3 py-1.5 rounded font-medium"
            style={{
              background: "var(--accent, #4f8ef7)",
              color: "#fff",
              textDecoration: "none",
            }}
          >
            ⬇ Download STL
          </a>
        )}
        <a
          href={scad_url}
          download
          className="text-xs px-3 py-1.5 rounded font-medium"
          style={{
            background: "var(--chat-border, #2a2d38)",
            color: "var(--chat-text, #e2e6f0)",
            textDecoration: "none",
          }}
        >
          ⬇ Download SCAD
        </a>
        <button
          onClick={() => setShowSource((v) => !v)}
          className="text-xs px-3 py-1.5 rounded font-medium ml-auto"
          style={{
            background: showSource ? "var(--accent-dim, #2a4a8a)" : "var(--chat-border, #2a2d38)",
            color: showSource ? "var(--accent, #4f8ef7)" : "var(--chat-muted, #6b7280)",
            border: "none",
            cursor: "pointer",
          }}
        >
          {showSource ? "Hide source" : "View source"}
        </button>
      </div>

      {/* OpenSCAD source */}
      {showSource && (
        <div className="px-3 pb-3">
          <ScadSource source={scad_source} />
        </div>
      )}
    </div>
  );
}
