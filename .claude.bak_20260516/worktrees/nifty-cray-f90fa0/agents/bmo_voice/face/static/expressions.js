/* ============================================================
   BMO Expressions — Numeric parameter definitions for each face state.

   Each expression is a set of values that define eye shape, position,
   mouth curvature, and special effects. The face renderer (face.js)
   interpolates between these values for smooth transitions.

   Coordinate system:
     - All values are normalized (0.0 to 1.0) relative to canvas size
     - (0, 0) is top-left, (1, 1) is bottom-right
     - Eye/mouth positions are relative to face center
   ============================================================ */

const BMO_EXPRESSIONS = {
  neutral: {
    // 1024x600 correction: Width needs to be smaller % to match Height % for circles.
    // BMO Eyes are vertical dots. 
    // H=0.08 (48px). W should be ~30px -> 0.03.
    leftEye: { x: -0.18, y: -0.10, width: 0.03, height: 0.08, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.10, width: 0.03, height: 0.08, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.15, // Lower down
      width: 0.05, // Narrower mouth (50px)
      curve: 0.2, // Subtle smile
      openness: 0.0,
      style: "arc",
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: false,
    glitch: false,
  },

  happy: {
    // Happy BMO often has curved eyes (inverted U) but we'll stick to oval for now, maybe shorter/wider?
    // Let's keep them vertical ovals but slightly lifted.
    leftEye: { x: -0.18, y: -0.13, width: 0.03, height: 0.085, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.13, width: 0.03, height: 0.085, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.12,
      width: 0.1, // Wider smile
      curve: 0.5,
      openness: 0.1, // Toothless open smile
      style: "arc",
    },

    blush: 0.3,
    sparkle: false,
    bounce: 0.015,
    zzz: false,
    glitch: false,
  },

  sad: {
    leftEye: { x: -0.18, y: -0.07, width: 0.03, height: 0.08, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.07, width: 0.03, height: 0.08, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.19,
      width: 0.06,
      curve: -0.3,
      openness: 0.0,
      style: "arc",
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: false,
    glitch: false,
  },

  surprised: {
    leftEye: { x: -0.19, y: -0.11, width: 0.035, height: 0.09, openness: 1.0 },
    rightEye: { x: 0.19, y: -0.11, width: 0.035, height: 0.09, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.17,
      width: 0.04, // Small O
      curve: 0,
      openness: 0.4,
      style: "open",
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: false,
    glitch: false,
  },

  thinking: {
    leftEye: { x: -0.18, y: -0.10, width: 0.03, height: 0.085, openness: 1.0 },
    rightEye: { x: 0.22, y: -0.11, width: 0.03, height: 0.07, openness: 0.8 }, // One eye squint/offset
    pupilSize: 0,
    pupilOffsetX: 0, 
    pupilOffsetY: 0,

    mouth: {
      y: 0.17,
      width: 0.02, // Tiny mouth
      curve: 0,
      openness: 0.0,
      style: "arc",
      offsetX: 0.05,
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: false,
    glitch: false,
  },

  listening: {
    leftEye: { x: -0.18, y: -0.10, width: 0.032, height: 0.082, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.10, width: 0.032, height: 0.082, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.17,
      width: 0.05, // Alert mouth
      curve: 0.1,
      openness: 0.0,
      style: "arc",
    },

    blush: 0,
    sparkle: false,
    bounce: 0.005,
    zzz: false,
    glitch: false,
  },

  speaking: {
    leftEye: { x: -0.18, y: -0.10, width: 0.03, height: 0.08, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.10, width: 0.03, height: 0.08, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.15,
      width: 0.08,
      curve: 0.2,
      openness: 0.2, 
      style: "open",
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: false,
    glitch: false,
  },

  sleeping: {
     // Eyes: Flat lines
    leftEye: { x: -0.18, y: -0.07, width: 0.04, height: 0.01, openness: 0.0 },
    rightEye: { x: 0.18, y: -0.07, width: 0.04, height: 0.01, openness: 0.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.15,
      width: 0.03,
      curve: 0.0,
      openness: 0.0,
      style: "arc",
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: true,
    glitch: false,
  },

  error: {
    leftEye: { x: -0.18, y: -0.10, width: 0.04, height: 0.09, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.09, width: 0.02, height: 0.03, openness: 0.8 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.17,
      width: 0.08,
      curve: 0,
      openness: 0.0,
      style: "zigzag",
    },

    blush: 0,
    sparkle: false,
    bounce: 0,
    zzz: false,
    glitch: true,
  },

  excited: {
    leftEye: { x: -0.18, y: -0.13, width: 0.035, height: 0.09, openness: 1.0 },
    rightEye: { x: 0.18, y: -0.13, width: 0.035, height: 0.09, openness: 1.0 },
    pupilSize: 0,
    pupilOffsetX: 0,
    pupilOffsetY: 0,

    mouth: {
      y: 0.13,
      width: 0.12,
      curve: 0.7,
      openness: 0.3,
      style: "arc",
    },

    blush: 0.8,
    sparkle: true,
    bounce: 0.02,
    zzz: false,
    glitch: false,
  },
};

// Make available globally
window.BMO_EXPRESSIONS = BMO_EXPRESSIONS;
