"use client";

import { useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { usePalaceStore } from "@/lib/stores/palace-store";

/**
 * First-person camera controller.
 * - Predefined positions per palace level.
 * - Smooth lerp transitions between positions (~0.8s).
 * - Subtle mouse parallax (±5°) for immersion.
 * - Breathing animation for ambient life.
 * - Dramatic entrance swoop on first load.
 */

const POSITIONS: Record<string, { pos: THREE.Vector3; target: THREE.Vector3 }> = {
  lobby: {
    pos: new THREE.Vector3(0, 1.6, 6),
    target: new THREE.Vector3(0, 1.2, 0),
  },
  wing: {
    pos: new THREE.Vector3(0, 1.6, 5),
    target: new THREE.Vector3(0, 1.2, -4),
  },
  hall: {
    pos: new THREE.Vector3(0, 1.6, 3),
    target: new THREE.Vector3(0, 1.0, -2),
  },
  room: {
    pos: new THREE.Vector3(0, 1.6, 3),
    target: new THREE.Vector3(0, 1.0, -2),
  },
};

// Entrance swoop: camera starts high & far, descends to lobby position
const ENTRANCE_START = new THREE.Vector3(0, 6, 14);
const ENTRANCE_LOOK_START = new THREE.Vector3(0, 2.5, -4);
const ENTRANCE_DURATION = 2.2; // seconds

const LERP_SPEED = 3.5;
const PARALLAX_STRENGTH = 0.065; // radians (~3.7° max, wider than before)
const PARALLAX_ROLL = 0.008; // subtle camera roll from mouse X

// Breathing – imperceptible consciously but creates life
const BREATH_AMPLITUDE = 0.008;
const BREATH_FREQ = 0.4; // Hz
const BREATH_SWAY_X = 0.003; // very subtle lateral sway

export function CameraController() {
  const { camera, gl } = useThree();
  const location = usePalaceStore((s) => s.location);
  const setTransitioning = usePalaceStore((s) => s.setTransitioning);

  const targetPos = useRef(new THREE.Vector3(0, 1.6, 6));
  const lookTarget = useRef(new THREE.Vector3(0, 1.2, 0));
  const mouse = useRef({ x: 0, y: 0 });
  const hasSettled = useRef(false);
  const entranceTime = useRef(0);
  const entranceDone = useRef(false);
  const firstFrame = useRef(true);

  // Update mouse position for parallax
  const onMouseMove = useRef((e: MouseEvent) => {
    const rect = gl.domElement.getBoundingClientRect();
    mouse.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  });

  // Register mouse listener once
  useFrame(() => {
    const dom = gl.domElement;
    dom.removeEventListener("mousemove", onMouseMove.current);
    dom.addEventListener("mousemove", onMouseMove.current);
  });

  useFrame((state, delta) => {
    const elapsed = state.clock.elapsedTime;

    // ── Entrance swoop ──────────────────────────────────────────────
    if (firstFrame.current) {
      firstFrame.current = false;
      camera.position.copy(ENTRANCE_START);
    }

    if (!entranceDone.current) {
      entranceTime.current += delta;
      // Smooth ease-out cubic
      const t = Math.min(entranceTime.current / ENTRANCE_DURATION, 1);
      const ease = 1 - Math.pow(1 - t, 3);

      const preset = POSITIONS.lobby;
      camera.position.lerpVectors(ENTRANCE_START, preset.pos, ease);
      const entranceLook = ENTRANCE_LOOK_START.clone().lerp(preset.target, ease);
      camera.lookAt(entranceLook);

      if (t >= 1) {
        entranceDone.current = true;
        setTransitioning(false);
      }
      return;
    }

    // ── Normal navigation ──────────────────────────────────────────
    const preset = POSITIONS[location.level] || POSITIONS.lobby;
    targetPos.current.copy(preset.pos);
    lookTarget.current.copy(preset.target);

    // Breathing animation — add subtle Y oscillation and lateral sway
    const breathY = Math.sin(elapsed * Math.PI * 2 * BREATH_FREQ) * BREATH_AMPLITUDE;
    const breathX = Math.sin(elapsed * Math.PI * 2 * BREATH_FREQ * 0.7) * BREATH_SWAY_X;
    targetPos.current.y += breathY;
    targetPos.current.x += breathX;

    // Lerp camera position
    camera.position.lerp(targetPos.current, 1 - Math.exp(-LERP_SPEED * delta));

    // Lerp look target with enhanced parallax
    const parallaxOffset = new THREE.Vector3(
      mouse.current.x * PARALLAX_STRENGTH,
      mouse.current.y * PARALLAX_STRENGTH * 0.5,
      0,
    );
    const finalTarget = lookTarget.current.clone().add(parallaxOffset);
    camera.lookAt(finalTarget);

    // Subtle camera roll from horizontal mouse position
    camera.rotation.z += (-mouse.current.x * PARALLAX_ROLL - camera.rotation.z) * delta * 3;

    // Detect when transition settles
    const dist = camera.position.distanceTo(targetPos.current);
    if (dist < 0.01 && !hasSettled.current) {
      hasSettled.current = true;
      setTransitioning(false);
    } else if (dist >= 0.01) {
      hasSettled.current = false;
    }
  });

  return null;
}
