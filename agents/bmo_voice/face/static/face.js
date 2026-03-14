/* ============================================================
   BMO Face Renderer — Canvas animation engine

   Draws BMO's face on an HTML5 Canvas with smooth interpolation
   between expression states, idle blinking, mouth sync animation,
   and special effects (blush, sparkles, zzz, glitch).

   Receives expression commands via WebSocket from the Python backend.
   ============================================================ */

(function () {
  "use strict";

  // ---- Canvas setup ----
  const canvas = document.getElementById("bmo-face");
  const ctx = canvas.getContext("2d");

  function resize() {
    // Render at half resolution for Pi performance
    const scale = 0.5;
    canvas.width = Math.round(window.innerWidth * scale);
    canvas.height = Math.round(window.innerHeight * scale);
    canvas.style.width = window.innerWidth + "px";
    canvas.style.height = window.innerHeight + "px";
    // Disable image smoothing for crisp pixel art look
    ctx.imageSmoothingEnabled = false;
  }
  window.addEventListener("resize", resize);
  resize();

  // ---- Colors (Authentic BMO) ----
  const COLORS = {
    bg: "#8bbe93", // BMO's authentic teal
    eyeWhite: "#000000", // Pure black eyes
    eyeShine: "rgba(255, 255, 255, 0.8)", // Subtle shine
    pupil: "#000000", 
    mouth: "#000000", // Black mouth
    blush: "rgba(255, 130, 150, 0.5)", 
    sparkle: "#ffffff",
    zzz: "rgba(26, 26, 46, 0.6)",
    text: "#1a1a2e",
    scanline: "rgba(0, 0, 0, 0.04)",
  };

  // ---- State ----
  let currentExpression = "neutral";
  // Safety check for BMO_EXPRESSIONS
  const startState = window.BMO_EXPRESSIONS ? window.BMO_EXPRESSIONS.neutral : {
    leftEye: { x: -0.12, y: -0.08, width: 0.065, height: 0.085, openness: 1.0 },
    rightEye: { x: 0.12, y: -0.08, width: 0.065, height: 0.085, openness: 1.0 },
    pupilSize: 0, pupilOffsetX: 0, pupilOffsetY: 0,
    mouth: { y: 0.08, width: 0.08, curve: 0.15, openness: 0, style: "arc" },
    blush: 0, sparkle: false, bounce: 0, zzz: false, glitch: false
  };

  let current = deepClone(startState);
  let target = deepClone(startState);

  let blinkTimer = randomBlink();
  let blinkState = 0; // 0 = open, 1 = closing, 2 = closed, 3 = opening
  let blinkProgress = 0;

  let mouthSyncData = null;
  let mouthSyncIndex = 0;
  let mouthSyncTimer = 0;

  let time = 0;
  let glitchTimer = 0;

  // ---- WebSocket ----
  let ws = null;
  let wsReconnectDelay = 1000;

  function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("BMO Face: WebSocket connected");
      wsReconnectDelay = 1000;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.error("BMO Face: Invalid message", e);
      }
    };

    ws.onclose = () => {
      console.log(
        `BMO Face: WebSocket closed, reconnecting in ${wsReconnectDelay}ms`,
      );
      setTimeout(connectWebSocket, wsReconnectDelay);
      wsReconnectDelay = Math.min(wsReconnectDelay * 1.5, 10000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function handleMessage(msg) {
    if (msg.type === "expression") {
      setExpression(msg.value, msg.mouth_sync || null);
    } else if (msg.type === "text") {
      showText(msg.value);
    }
  }

  // ---- Expression control ----
  function setExpression(name, mouthSync) {
    if (!window.BMO_EXPRESSIONS || !window.BMO_EXPRESSIONS[name]) {
      console.warn(`BMO Face: Unknown expression "${name}"`);
      return;
    }

    currentExpression = name;
    target = deepClone(window.BMO_EXPRESSIONS[name]);

    if (mouthSync) {
      mouthSyncData = mouthSync;
      mouthSyncIndex = 0;
      mouthSyncTimer = 0;
    } else {
      mouthSyncData = null;
    }

    console.log(`BMO Face: Expression → ${name}`);
  }

  // ---- Text display ----
  function showText(text) {
    const el = document.getElementById("text-display");
    if (!text) {
      el.classList.add("hidden");
      return;
    }
    el.textContent = text;
    el.classList.remove("hidden");

    // Auto-hide after 5 seconds
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => {
      el.classList.add("hidden");
    }, 5000);
  }

  // ---- Touch-to-wake ----
  canvas.addEventListener("click", () => {
    // Send touch event to backend
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "touch", action: "wake" }));
    }

    // Show visual feedback
    const overlay = document.getElementById("touch-overlay");
    overlay.classList.remove("hidden");
    setTimeout(() => overlay.classList.add("hidden"), 2000);
  });

  // ---- Interpolation helpers ----
  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function lerpEye(curr, tgt, t) {
    return {
      x: lerp(curr.x, tgt.x, t),
      y: lerp(curr.y, tgt.y, t),
      width: lerp(curr.width, tgt.width, t),
      height: lerp(curr.height, tgt.height, t),
      openness: lerp(curr.openness, tgt.openness, t),
    };
  }

  function lerpMouth(curr, tgt, t) {
    return {
      y: lerp(curr.y, tgt.y, t),
      width: lerp(curr.width, tgt.width, t),
      curve: lerp(curr.curve, tgt.curve, t),
      openness: lerp(curr.openness, tgt.openness, t),
      style: tgt.style,
      offsetX: lerp(curr.offsetX || 0, tgt.offsetX || 0, t),
    };
  }

  function lerpState(curr, tgt, t) {
    return {
      leftEye: lerpEye(curr.leftEye, tgt.leftEye, t),
      rightEye: lerpEye(curr.rightEye, tgt.rightEye, t),
      pupilSize: lerp(curr.pupilSize || 0, tgt.pupilSize || 0, t),
      pupilOffsetX: lerp(curr.pupilOffsetX || 0, tgt.pupilOffsetX || 0, t),
      pupilOffsetY: lerp(curr.pupilOffsetY || 0, tgt.pupilOffsetY || 0, t),
      mouth: lerpMouth(curr.mouth, tgt.mouth, t),
      blush: lerp(curr.blush, tgt.blush, t),
      sparkle: tgt.sparkle,
      bounce: lerp(curr.bounce, tgt.bounce, t),
      zzz: tgt.zzz,
      glitch: tgt.glitch,
    };
  }

  function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function randomBlink() {
    return 3000 + Math.random() * 4000; // 3-7 seconds
  }

  // ---- Drawing functions ----
  function drawEye(cx, cy, w, h, openness, pupilSz, pOffX, pOffY) {
    const absW = w * canvas.width;
    const absH = h * canvas.height * openness;

    if (openness < 0.05) {
      // Closed eye — draw a line
      ctx.strokeStyle = COLORS.eyeWhite;
      ctx.lineWidth = 4;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(cx - absW * 0.8, cy);
      ctx.lineTo(cx + absW * 0.8, cy);
      ctx.stroke();
      return;
    }

    // Eye shape (simple black vertical oval)
    ctx.fillStyle = COLORS.eyeWhite;
    ctx.beginPath();
    ctx.ellipse(cx, cy, absW, absH, 0, 0, Math.PI * 2);
    ctx.fill();

    // No shine for authentic "LCD" BMO look

  }

  function drawMouthArc(cx, cy, w, curve, openness) {
    const absW = w * canvas.width;
    const absCurve = curve * canvas.height * 0.3;

    ctx.strokeStyle = COLORS.mouth;
    ctx.lineWidth = 3.5;
    ctx.lineCap = "round";

    if (openness > 0.05) {
      // Open mouth — filled shape
      const absOpen = openness * canvas.height * 0.06;

      ctx.fillStyle = COLORS.mouth;
      ctx.beginPath();
      ctx.moveTo(cx - absW, cy);
      // Top curve
      ctx.quadraticCurveTo(cx, cy + absCurve, cx + absW, cy);
      // Bottom curve (wider opening)
      ctx.quadraticCurveTo(cx, cy + absCurve + absOpen, cx - absW, cy);
      ctx.fill();
    } else {
      // Closed mouth — just a curved line
      ctx.beginPath();
      ctx.moveTo(cx - absW, cy);
      ctx.quadraticCurveTo(cx, cy + absCurve, cx + absW, cy);
      ctx.stroke();
    }
  }

  function drawMouthOpen(cx, cy, w, openness) {
    // Round open mouth (surprised)
    const absW = w * canvas.width;
    const absH = openness * canvas.height * 0.06;

    ctx.fillStyle = COLORS.mouth;
    ctx.beginPath();
    ctx.ellipse(cx, cy, absW, Math.max(absH, absW * 0.3), 0, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawMouthZigzag(cx, cy, w) {
    // Zigzag / squiggly mouth (error/confused)
    const absW = w * canvas.width;
    const segments = 5;
    const segW = (absW * 2) / segments;
    const amp = canvas.height * 0.012;

    ctx.strokeStyle = COLORS.mouth;
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    ctx.beginPath();
    ctx.moveTo(cx - absW, cy);
    for (let i = 1; i <= segments; i++) {
      const x = cx - absW + segW * i;
      const y = cy + (i % 2 === 0 ? -amp : amp);
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function drawMouth(state) {
    const m = state.mouth;
    const cx = canvas.width / 2 + (m.offsetX || 0) * canvas.width;
    const cy = canvas.height / 2 + m.y * canvas.height;

    switch (m.style) {
      case "arc":
        drawMouthArc(cx, cy, m.width, m.curve, m.openness);
        break;
      case "open":
        drawMouthOpen(cx, cy, m.width, m.openness);
        break;
      case "zigzag":
        drawMouthZigzag(cx, cy, m.width);
        break;
      default:
        drawMouthArc(cx, cy, m.width, m.curve, m.openness);
    }
  }

  function drawBlush(state) {
    if (state.blush < 0.01) return;

    const alpha = state.blush * 0.45;
    const r = canvas.width * 0.04;
    const cy = canvas.height / 2 - canvas.height * 0.02;

    // Left blush
    ctx.fillStyle = `rgba(255, 130, 150, ${alpha})`;
    ctx.beginPath();
    ctx.ellipse(
      canvas.width / 2 - canvas.width * 0.18,
      cy,
      r,
      r * 0.6,
      0,
      0,
      Math.PI * 2,
    );
    ctx.fill();

    // Right blush
    ctx.beginPath();
    ctx.ellipse(
      canvas.width / 2 + canvas.width * 0.18,
      cy,
      r,
      r * 0.6,
      0,
      0,
      Math.PI * 2,
    );
    ctx.fill();
  }

  function drawSparkles() {
    const now = time * 0.002;
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;

    for (let i = 0; i < 6; i++) {
      const angle = now * 1.5 + (i * Math.PI * 2) / 6;
      const dist = canvas.width * (0.2 + Math.sin(now + i) * 0.05);
      const x = cx + Math.cos(angle) * dist;
      const y = cy - canvas.height * 0.1 + Math.sin(angle) * dist * 0.4;
      const size = 3 + Math.sin(now * 3 + i * 2) * 2;
      const alpha = 0.4 + Math.sin(now * 4 + i) * 0.4;

      ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
      drawStar(x, y, size);
    }
  }

  function drawStar(x, y, r) {
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      const angle = (Math.PI / 2) * i;
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(angle) * r, y + Math.sin(angle) * r);
    }
    ctx.lineWidth = 2;
    ctx.strokeStyle = ctx.fillStyle;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(x, y, r * 0.3, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawZzz(state) {
    if (!state.zzz) return;

    const zzzTime = time * 0.0005; 
    const cx = canvas.width / 2 + canvas.width * 0.18;
    const baseY = canvas.height / 2 - canvas.height * 0.12;

    const sizes = [10, 14, 18];
    for (let i = 0; i < 3; i++) {
      // Drifting Zs
      const cycle = (zzzTime + i * 0.33) % 1; 
      const yOff = -cycle * 90; 
      const alpha = 1.0 - cycle; // Fade out as it goes up
      
      const xDrift = Math.sin(cycle * 3 + i) * 10;

      ctx.font = `${sizes[i]}px 'Press Start 2P', monospace`;
      ctx.fillStyle = `rgba(26, 26, 46, ${alpha})`;
      ctx.fillText("z", cx + xDrift + i * 15, baseY + yOff);
    }
  }

  function drawScanlines() {
    // Subtle CRT scanline effect — reduced frequency for Pi performance
    ctx.fillStyle = COLORS.scanline;
    for (let y = 0; y < canvas.height; y += 8) {
      ctx.fillRect(0, y, canvas.width, 1);
    }
  }

  function drawGlitch(state) {
    // Disabled on Pi for performance (getImageData is very expensive)
    return;
  }

  // ---- Blink logic ----
  function updateBlink(dt) {
    // Don't blink if sleeping or mid-expression-change
    if (currentExpression === "sleeping") return;

    blinkTimer -= dt;

    if (blinkTimer <= 0 && blinkState === 0) {
      blinkState = 1; // Start closing
      blinkProgress = 0;
    }

    if (blinkState > 0) {
      blinkProgress += dt * 0.008; // Speed of blink

      if (blinkState === 1 && blinkProgress >= 1) {
        blinkState = 2; // Fully closed
        blinkProgress = 0;
        setTimeout(() => {
          blinkState = 3;
        }, 60); // Stay closed briefly
      }

      if (blinkState === 3 && blinkProgress >= 1) {
        blinkState = 0; // Done
        blinkProgress = 0;
        blinkTimer = randomBlink();
      }
    }
  }

  function getBlinkOpenness() {
    if (blinkState === 0) return 1.0;
    if (blinkState === 1) return 1.0 - blinkProgress; // Closing
    if (blinkState === 2) return 0.0; // Closed
    if (blinkState === 3) return Math.min(blinkProgress, 1); // Opening
    return 1.0;
  }

  // ---- Mouth sync ----
  function updateMouthSync(dt) {
    if (!mouthSyncData || mouthSyncData.length === 0) return;

    mouthSyncTimer += dt;
    const frameDuration = 80; // ms per amplitude frame

    if (mouthSyncTimer >= frameDuration) {
      mouthSyncTimer -= frameDuration;
      mouthSyncIndex++;

      if (mouthSyncIndex >= mouthSyncData.length) {
        mouthSyncData = null;
        mouthSyncIndex = 0;
        return;
      }
    }

    // Override mouth openness with sync data
    if (mouthSyncData && mouthSyncIndex < mouthSyncData.length) {
      target.mouth.openness = mouthSyncData[mouthSyncIndex] * 0.8;
    }
  }

  // ---- Main render loop ----
  let lastTime = 0;
  const FPS_LIMIT = 12;
  const FRAME_MIN_TIME = 1000 / FPS_LIMIT;
  let lastFrameTime = 0;

  function render(timestamp) {
    requestAnimationFrame(render); // Schedule next frame immediately

    // Throttle FPS
    if (timestamp - lastFrameTime < FRAME_MIN_TIME) {
        return;
    }
    const dt = timestamp - lastFrameTime;
    lastFrameTime = timestamp;
    
    // Update global time for animations
    time = timestamp;

    // Interpolate toward target
    const speed = 0.08; // Lower = smoother, higher = snappier
    current = lerpState(current, target, speed);

    // Update subsystems
    updateBlink(dt);
    updateMouthSync(dt);

    // Clear
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Bounce offset
    const bounceY = Math.sin(time * 0.006) * (current.bounce || 0) * canvas.height;

    ctx.save();
    ctx.translate(0, bounceY);

    // Draw face elements
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const blinkOpen = getBlinkOpenness();

    // Left eye
    const le = current.leftEye;
    drawEye(
      centerX + le.x * canvas.width,
      centerY + le.y * canvas.height,
      le.width,
      le.height,
      le.openness * blinkOpen,
      current.pupilSize || 0,
      current.pupilOffsetX || 0,
      current.pupilOffsetY || 0,
    );

    // Right eye
    const re = current.rightEye;
    drawEye(
      centerX + re.x * canvas.width,
      centerY + re.y * canvas.height,
      re.width,
      re.height,
      re.openness * blinkOpen,
      current.pupilSize || 0,
      current.pupilOffsetX || 0,
      current.pupilOffsetY || 0,
    );

    // Mouth
    drawMouth(current);

    ctx.restore();
  }

  // ---- Chat Input ----
  function setupInput() {
    const input = document.getElementById("chat-input");
    if (!input) return;

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const text = input.value.trim();
        if (text) {
          // Send to backend
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "chat", text: text }));
            input.value = "";
            // Optional: Show pending state on face?
            setExpression("listening");
          } else {
            console.warn("WebSocket not connected");
          }
        }
      }
    });
  }

  // ---- Boot ----
  function init() {
    console.log("BMO Face: Initializing...");

    // Connect WebSocket
    connectWebSocket();

    // Setup Input
    setupInput();

    // Start render loop
    requestAnimationFrame(render);

    console.log("BMO Face: Ready! ✨");
  }

  // ---- Demo mode (for testing without backend) ----
  window.BMO = {
    setExpression: (name, mouthSync) => setExpression(name, mouthSync),
    showText: (text) => showText(text),
    demo: async () => {
      if (!window.BMO_EXPRESSIONS) return;
      const expressions = Object.keys(window.BMO_EXPRESSIONS);
      for (const expr in expressions) {
        setExpression(expressions[expr]);
        await new Promise((r) => setTimeout(r, 2500));
      }
      setExpression("neutral");
    },
  };

  init();
})();
