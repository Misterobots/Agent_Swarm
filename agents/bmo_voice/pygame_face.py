"""
BMO Face — Native Pygame Renderer

Replaces browser-based face with direct GPU rendering via SDL2.
Runs fullscreen on the Raspberry Pi with minimal resource usage.

Usage:
  face = PygameFace()
  face.start()  # Starts in background thread
  face.set_expression("happy")
  face.set_expression("speaking")
  face.stop()
"""

import os
import numpy as np

# Suppress pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame
import threading
import queue
import math
import time
import random
import copy
import logging

logger = logging.getLogger("bmo_face")

# ─── Colors ───
BMO_TEAL = (139, 190, 147)   #8bbe93
BLACK = (0, 0, 0)

def _quadratic_bezier(p0, p1, p2, steps=10):
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t)**2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t)**2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        points.append((int(x), int(y)))
    return points

# ─── Expression Definitions ───
# Ported from expressions.js — all values normalized to screen dimensions
EXPRESSIONS = {
    "neutral": {
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.03, "height": 0.08, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.10, "width": 0.03, "height": 0.08, "openness": 1.0},
        "mouth": {"y": 0.15, "width": 0.05, "curve": 0.2, "openness": 0.0, "style": "arc", "offsetX": 0.02},
        "bounce": 0,
    },
    "happy": {
        "leftEye":  {"x": -0.28, "y": -0.13, "width": 0.03, "height": 0.085, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.13, "width": 0.03, "height": 0.085, "openness": 1.0},
        "mouth": {"y": 0.12, "width": 0.1, "curve": 0.5, "openness": 0.1, "style": "arc", "offsetX": 0.02},
        "bounce": 0.015,
    },
    "sad": {
        "leftEye":  {"x": -0.28, "y": -0.07, "width": 0.03, "height": 0.08, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.07, "width": 0.03, "height": 0.08, "openness": 1.0},
        "mouth": {"y": 0.19, "width": 0.06, "curve": -0.3, "openness": 0.0, "style": "arc", "offsetX": 0.02},
        "bounce": 0,
    },
    "surprised": {
        "leftEye":  {"x": -0.29, "y": -0.11, "width": 0.035, "height": 0.09, "openness": 1.0},
        "rightEye": {"x":  0.29, "y": -0.11, "width": 0.035, "height": 0.09, "openness": 1.0},
        "mouth": {"y": 0.17, "width": 0.04, "curve": 0, "openness": 0.4, "style": "open", "offsetX": 0.02},
        "bounce": 0,
    },
    "thinking": {
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.03, "height": 0.085, "openness": 1.0},
        "rightEye": {"x":  0.32, "y": -0.11, "width": 0.03, "height": 0.04,  "openness": 0.6},
        "mouth": {"y": 0.17, "width": 0.02, "curve": 0, "openness": 0.0, "style": "arc", "offsetX": 0.07},
        "bounce": 0,
    },
    "listening": {
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.032, "height": 0.082, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.10, "width": 0.032, "height": 0.082, "openness": 1.0},
        "mouth": {"y": 0.17, "width": 0.05, "curve": 0.1, "openness": 0.0, "style": "arc", "offsetX": 0.02},
        "bounce": 0.005,
    },
    "speaking": {
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.03, "height": 0.08, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.10, "width": 0.03, "height": 0.08, "openness": 1.0},
        "mouth": {"y": 0.15, "width": 0.08, "curve": 0.2, "openness": 0.2, "style": "open", "offsetX": 0.02},
        "bounce": 0,
    },
    "sleeping": {
        "leftEye":  {"x": -0.28, "y": -0.07, "width": 0.04, "height": 0.01, "openness": 0.0},
        "rightEye": {"x":  0.28, "y": -0.07, "width": 0.04, "height": 0.01, "openness": 0.0},
        "mouth": {"y": 0.15, "width": 0.03, "curve": 0.0, "openness": 0.0, "style": "arc", "offsetX": 0.02},
        "bounce": 0,
    },
    "error": {
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.04, "height": 0.09, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.09, "width": 0.02, "height": 0.03, "openness": 0.8},
        "mouth": {"y": 0.17, "width": 0.08, "curve": 0, "openness": 0.0, "style": "zigzag", "offsetX": 0.02},
        "bounce": 0,
    },
    "acknowledged": {
        # Wake word detected — eyes widen with gentle bounce (distinct from "listening" or "surprised")
        "leftEye":  {"x": -0.28, "y": -0.12, "width": 0.034, "height": 0.09, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.12, "width": 0.034, "height": 0.09, "openness": 1.0},
        "mouth": {"y": 0.14, "width": 0.06, "curve": 0.35, "openness": 0.0, "style": "arc", "offsetX": 0.02},
        "bounce": 0.025,
    },
    "excited": {
        "leftEye":  {"x": -0.28, "y": -0.13, "width": 0.035, "height": 0.09, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.13, "width": 0.035, "height": 0.09, "openness": 1.0},
        "mouth": {"y": 0.13, "width": 0.12, "curve": 0.7, "openness": 0.3, "style": "arc", "offsetX": 0.02},
        "bounce": 0.02,
    },
    
    # --- Speaking Variants ---
    
    "happy_speaking": {
        # Happy Eyes (Squintier)
        "leftEye":  {"x": -0.28, "y": -0.13, "width": 0.035, "height": 0.06, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.13, "width": 0.035, "height": 0.06, "openness": 1.0},
        # Speaking Mouth (Big Smile)
        "mouth": {"y": 0.14, "width": 0.1, "curve": 0.6, "openness": 0.2, "style": "open", "offsetX": 0.02},
        "bounce": 0.03, # More bounce
    },
    "sad_speaking": {
        # Sad Eyes (Droopier)
        "leftEye":  {"x": -0.28, "y": -0.06, "width": 0.03, "height": 0.08, "openness": 0.9},
        "rightEye": {"x":  0.28, "y": -0.06, "width": 0.03, "height": 0.08, "openness": 0.9},
        # Speaking Mouth (Deep Frown)
        "mouth": {"y": 0.16, "width": 0.08, "curve": -0.5, "openness": 0.2, "style": "open", "offsetX": 0.02},
        "bounce": 0,
    },
    "excited_speaking": {
        # Excited Eyes (Wide)
        "leftEye":  {"x": -0.28, "y": -0.13, "width": 0.04, "height": 0.1, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.13, "width": 0.04, "height": 0.1, "openness": 1.0},
        # Speaking Mouth (Huge Open)
        "mouth": {"y": 0.13, "width": 0.12, "curve": 0.8, "openness": 0.4, "style": "open", "offsetX": 0.02},
        "bounce": 0.06, # Super bounce
    },
    "thinking_speaking": {
         # Thinking Eyes
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.03, "height": 0.085, "openness": 1.0},
        "rightEye": {"x":  0.32, "y": -0.11, "width": 0.03, "height": 0.04,  "openness": 0.6},
        # Speaking Mouth
        "mouth": {"y": 0.15, "width": 0.08, "curve": 0.1, "openness": 0.2, "style": "open", "offsetX": 0.02},
        "bounce": 0,       
    },
    "error_speaking": {
        "leftEye":  {"x": -0.28, "y": -0.10, "width": 0.04, "height": 0.09, "openness": 1.0},
        "rightEye": {"x":  0.28, "y": -0.09, "width": 0.02, "height": 0.03, "openness": 0.8},
        "mouth": {"y": 0.17, "width": 0.08, "curve": 0, "openness": 0.2, "style": "zigzag", "offsetX": 0.02},
        "bounce": 0,
    },
    "surprised_speaking": {
        "leftEye":  {"x": -0.29, "y": -0.11, "width": 0.035, "height": 0.09, "openness": 1.0},
        "rightEye": {"x":  0.29, "y": -0.11, "width": 0.035, "height": 0.09, "openness": 1.0},
        "mouth": {"y": 0.17, "width": 0.06, "curve": 0, "openness": 0.6, "style": "open", "offsetX": 0.02},
        "bounce": 0,
    },
    "sleeping_speaking": {
        "leftEye":  {"x": -0.28, "y": -0.07, "width": 0.04, "height": 0.01, "openness": 0.0},
        "rightEye": {"x":  0.28, "y": -0.07, "width": 0.04, "height": 0.01, "openness": 0.0},
        "mouth": {"y": 0.15, "width": 0.05, "curve": 0.0, "openness": 0.1, "style": "arc", "offsetX": 0.02},
        "bounce": 0,
    },
}


def _deep_clone(obj):
    return copy.deepcopy(obj)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_dict(current, target, t, keys):
    """Lerp numeric values in a dict."""
    for k in keys:
        if k in current and k in target:
            current[k] = _lerp(current[k], target[k], t)


def _quadratic_bezier(p0, p1, p2, steps=8):
    """Generate points along a quadratic Bezier curve."""
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        points.append((int(x), int(y)))
    return points


class PygameFace:
    """Native pygame face renderer for BMO."""

    def __init__(self, width=0, height=0, fps=30):
        """
        Args:
            width/height: 0 = use display resolution (fullscreen)
            fps: target frame rate
        """
        self.requested_width = width
        self.requested_height = height
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self._cmd_queue = queue.Queue()
        self._thread = None
        self._ready = threading.Event()

        # Animation state
        self.current = _deep_clone(EXPRESSIONS["neutral"])
        self.target = _deep_clone(EXPRESSIONS["neutral"])
        self.velocity = {
            "leftEye": {},
            "rightEye": {},
            "mouth": {},
            "bounce": 0.0
        }

        # Procedural Life State
        self.breath_timer = 0.0
        self.eye_drift = {"x": 0.0, "y": 0.0}
        self.eye_drift_timer = 2.0
        self.current_face_name = "neutral"

        # Blink
        self.blink_timer = 0
        self.blink_next = 3.0 + random.random() * 4.0
        self.blink_progress = 0
        self.is_blinking = False

        # Mouth sync
        self.mouth_sync_data = None
        self.mouth_sync_index = 0
        self.mouth_sync_timer = 0

        # Expression timeout safety (reset to neutral if stuck)
        self._expression_timeout = 30.0  # seconds
        self._expression_timer = 0.0

        # Mic level indicator (0–32767 int16 RMS)
        self.mic_rms = 0
        self._mic_rms_lock = threading.Lock()

        # Time
        self.time = 0

    # ─── Public API (thread-safe) ───

    def start(self):
        """Start the face renderer in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        logger.info("Pygame Face started")

    def set_expression(self, name, mouth_sync=None):
        """Thread-safe: change expression."""
        self._cmd_queue.put(("expression", name, mouth_sync))

    def set_mic_rms(self, value: int):
        """Thread-safe: update mic RMS level for the level indicator."""
        with self._mic_rms_lock:
            self.mic_rms = max(0, int(value))

    def stop(self):
        """Signal the renderer to stop."""
        self.running = False

    # Async-compatible wrappers (so bmo_driver.py doesn't need changes)
    async def send_expression(self, expression, mouth_sync=None):
        """Async wrapper for set_expression (drop-in for FaceServer)."""
        self.set_expression(expression, mouth_sync)

    async def send_text(self, text):
        """Placeholder for text display."""
        pass  # TODO: render text on face

    # ─── Main Loop ───

    def _run(self):
        """Main pygame loop (runs in thread)."""
        try:
            self._run_inner()
        except Exception as e:
            logger.error(f"Pygame Face CRASHED: {e}", exc_info=True)
            print(f"\n❌ FACE ERROR: {e}\n")
            self._ready.set()  # Unblock main thread

    def _run_inner(self):
        """Actual rendering loop — X11 with pygame.SCALED."""
        # Ensure DISPLAY is set for X11
        # Respect existing driver (e.g. kmsdrm)
        if 'SDL_VIDEODRIVER' not in os.environ:
            # Default to X11 logic if no driver is forced
            if 'DISPLAY' not in os.environ:
                os.environ['DISPLAY'] = ':0'
        else:
            logger.info(f"Using Configured Driver: {os.environ['SDL_VIDEODRIVER']}")

        pygame.display.init()
        driver_used = pygame.display.get_driver()
        logger.info(f"SDL Video Driver: {driver_used}")

        # Internal render resolution
        # KMSDRM is fast enough for native res on Pi 4
        self.width = 1024
        self.height = 600
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE

        try:
            screen = pygame.display.set_mode((self.width, self.height), flags)
        except pygame.error:
            # Fallback
            screen = pygame.display.set_mode((self.width, self.height), pygame.DOUBLEBUF)

        pygame.display.set_caption("BMO")
        pygame.mouse.set_visible(False)

        clock = pygame.time.Clock()
        self.running = True

        # Create an offscreen canvas for drawing upright
        # We will flip this onto the actual screen
        canvas = pygame.Surface((self.width, self.height))

        # Font for FPS counter
        pygame.font.init()
        try:
            fps_font = pygame.font.SysFont(None, 20)
        except Exception:
            fps_font = None

        self._ready.set()

        # FPS tracking
        frame_count = 0
        fps_timer = 0
        fps_display = 0.0

        logger.info(f"Pygame Face: {self.width}x{self.height} (driver: {driver_used})")

        while self.running:
            dt = clock.tick(self.fps) / 1000.0
            self.time += dt
            frame_count += 1
            fps_timer += dt

            # Update FPS every 2 seconds
            if fps_timer >= 2.0:
                fps_display = frame_count / fps_timer
                logger.info(f"FPS: {fps_display:.1f}")
                frame_count = 0
                fps_timer = 0

            # Process commands
            while not self._cmd_queue.empty():
                try:
                    cmd = self._cmd_queue.get_nowait()
                    self._handle_cmd(cmd)
                except queue.Empty:
                    break

            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

            # Update animations (time-based)
            self._update_procedural(dt)
            self._update_mouth_sync(dt)
            self._update_springs(dt)
            self._update_blink(dt)
            self._update_expression_timeout(dt)

            # Calculate bounce
            bounce = self.current.get("bounce", 0)
            bounce_y = int(math.sin(self.time * 6.0) * bounce * self.height)

            # --- Rendering to Canvas (Upright) ---
            canvas.fill(BMO_TEAL)
            
            # Draw face on canvas
            self._draw_face(canvas, bounce_y)

            # Draw mic level indicator (bottom-left corner)
            self._draw_mic_indicator(canvas)
            
            # FPS on canvas
            if fps_font and fps_display > 0:
                fps_text = fps_font.render(f"{fps_display:.0f}", True, BLACK)
                canvas.blit(fps_text, (4, 4))

            # --- Rotate and Display ---
            # 180 degree flip (Horizontal + Vertical flip is faster than rotate)
            flipped = pygame.transform.flip(canvas, True, True)
            
            # Blit to actual screen
            screen.blit(flipped, (0, 0))
            pygame.display.flip()

        pygame.quit()
        logger.info("Pygame Face stopped")

    def _draw_mic_indicator(self, surface):
        """Draw a small mic level bar in the bottom-left corner."""
        with self._mic_rms_lock:
            rms = self.mic_rms

        # Bar geometry (placed top-left in upright canvas; after 180° flip → bottom-right on screen)
        bar_x = 8
        bar_y = 8
        bar_w = 120
        bar_h = 18

        # Background
        pygame.draw.rect(surface, (0, 0, 0), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))

        # Fill level: scale RMS against practical speech max (~5000).
        # Silent ambient ≈ 200-400, quiet speech ≈ 1000, normal ≈ 3000, loud ≈ 5000+
        level = min(rms / 5000.0, 1.0)
        fill_w = int(bar_w * level)

        if fill_w > 0:
            # Color: green <25%, yellow 25–75%, red >75%
            if level < 0.25:
                color = (0, 220, 80)
            elif level < 0.75:
                color = (220, 200, 0)
            else:
                color = (220, 40, 40)
            pygame.draw.rect(surface, color, (bar_x, bar_y, fill_w, bar_h))

    def _handle_cmd(self, cmd):        try:
            # Handle variable length tuple depending on caller
            if len(cmd) == 3:
                kind, name, mouth_sync = cmd
            else:
                kind, name = cmd[0], cmd[1]
                mouth_sync = None
                
            if kind == "expression" and name in EXPRESSIONS:
                self.target = _deep_clone(EXPRESSIONS[name])
                self.current_face_name = name
                # Immediately update discrete style property (strings don't lerp)
                self.current["mouth"]["style"] = self.target["mouth"]["style"]
                # Reset expression timeout on every new command
                self._expression_timer = 0.0

                if mouth_sync:
                    self.mouth_sync_data = mouth_sync
                    self.mouth_sync_index = 0
                    self.mouth_sync_timer = 0
                else:
                    self.mouth_sync_data = None
        except Exception as e:
            logger.error(f"Error handling face command {cmd}: {e}")

    # ─── Animation ───

    def _spring_dict(self, current, target, velocity, keys, dt, tension=150.0, dampening=12.0):
        for k in keys:
            if k in current and k in target:
                curr = current[k]
                tgt = target[k]
                vel = velocity.setdefault(k, 0.0)
                
                # Spring physics logic
                force = (tgt - curr) * tension
                force -= vel * dampening
                vel += force * dt
                
                current[k] += vel * dt
                velocity[k] = vel

    def _update_springs(self, dt):
        """Physics-based spring interpolation for snapping and bouncing."""
        # Use a slightly stiffer spring for eyes
        for eye_key in ("leftEye", "rightEye"):
            self._spring_dict(self.current[eye_key], self.target[eye_key], self.velocity[eye_key],
                       ["x", "y", "width", "height", "openness"], dt, tension=180.0, dampening=14.0)

        # Mouth gets a slightly looser spring for squishy feel
        self._spring_dict(self.current["mouth"], self.target["mouth"], self.velocity["mouth"],
                   ["y", "width", "curve", "openness", "offsetX"], dt, tension=140.0, dampening=10.0)
                   
        self.current["mouth"]["style"] = self.target["mouth"]["style"]

        # Bounce spring
        curr_bounce = self.current.get("bounce", 0.0)
        tgt_bounce = self.target.get("bounce", 0.0)
        vel_bounce = self.velocity.get("bounce", 0.0)
        
        force = (tgt_bounce - curr_bounce) * 150.0
        force -= vel_bounce * 12.0
        vel_bounce += force * dt
        self.current["bounce"] = curr_bounce + vel_bounce * dt
        self.velocity["bounce"] = vel_bounce

    def _update_procedural(self, dt):
        """Injects life-like micro-animations (breathing, eye wandering)."""
        # Breathing (Subtle Y-axis shift and width pulsing)
        self.breath_timer += dt * 1.5
        breath_offset = math.sin(self.breath_timer) * 0.005
        
        # Apply breath offset non-destructively to target
        if "speaking" not in self.current_face_name:
             self.target["mouth"]["width"] = EXPRESSIONS.get(self.current_face_name, EXPRESSIONS["neutral"])["mouth"]["width"] + (breath_offset * 1.5)
        
        # Eye Wandering (only in thinking or idle)
        if self.current_face_name in ["thinking", "neutral", "listening"]:
            self.eye_drift_timer -= dt
            if self.eye_drift_timer <= 0:
                # Pick a new random drift spot
                self.eye_drift["x"] = random.uniform(-0.015, 0.015)
                self.eye_drift["y"] = random.uniform(-0.015, 0.015)
                self.eye_drift_timer = random.uniform(1.0, 4.0)
        else:
            self.eye_drift["x"] = 0.0
            self.eye_drift["y"] = 0.0
            
        # Apply drift target
        base_exp = EXPRESSIONS.get(self.current_face_name, EXPRESSIONS["neutral"])
        for eye in ["leftEye", "rightEye"]:
             self.target[eye]["x"] = base_exp[eye]["x"] + self.eye_drift["x"]
             self.target[eye]["y"] = base_exp[eye]["y"] + self.eye_drift["y"] + breath_offset

    def _update_blink(self, dt):
        """Natural blink cycle."""
        if self.is_blinking:
            self.blink_progress += dt * 8  # Speed of blink
            if self.blink_progress >= 1.0:
                self.is_blinking = False
                self.blink_progress = 0
                self.blink_timer = 0
                self.blink_next = 3.0 + random.random() * 4.0
        else:
            self.blink_timer += dt
            if self.blink_timer >= self.blink_next:
                self.is_blinking = True
                self.blink_progress = 0

    def _update_expression_timeout(self, dt):
        """Safety reset: if face is stuck in a non-neutral state too long, reset."""
        if self.current_face_name != "neutral":
            self._expression_timer += dt
            if self._expression_timer >= self._expression_timeout:
                logger.warning(f"Expression timeout! Stuck in '{self.current_face_name}' for {self._expression_timeout}s. Resetting to neutral.")
                self.target = _deep_clone(EXPRESSIONS["neutral"])
                self.current_face_name = "neutral"
                self.current["mouth"]["style"] = "arc"
                self._expression_timer = 0.0
        else:
            self._expression_timer = 0.0

    def _get_blink_openness(self):
        """Returns 0.0 (closed) to 1.0 (open)."""
        if not self.is_blinking:
            return 1.0
        # Smooth blink: close then open
        p = self.blink_progress
        if p < 0.4:
            return 1.0 - (p / 0.4)
        elif p < 0.6:
            return 0.0
        else:
            return (p - 0.6) / 0.4

    def _update_mouth_sync(self, dt):
        """Dynamic phonetic mapping based on volume amplitude."""
        if self.mouth_sync_data is None:
            # If not speaking, ensure mouth returns to base expression
            base_exp = EXPRESSIONS.get(self.current_face_name, EXPRESSIONS["neutral"])
            self.target["mouth"]["openness"] = base_exp["mouth"]["openness"]
            self.target["mouth"]["width"] = base_exp["mouth"]["width"]
            self.target["mouth"]["curve"] = base_exp["mouth"]["curve"]
            return

        self.mouth_sync_timer += dt
        frame_dur = 0.05  # Faster phonetic parsing (20fps)

        if self.mouth_sync_timer >= frame_dur:
            self.mouth_sync_timer = 0
            self.mouth_sync_index += 1

            if self.mouth_sync_index >= len(self.mouth_sync_data):
                self.mouth_sync_data = None
                return

            val = self.mouth_sync_data[self.mouth_sync_index]
            
            # Map amplitude to phonetic shapes!
            base_exp = EXPRESSIONS.get(self.current_face_name, EXPRESSIONS["neutral"])
            base_width = base_exp["mouth"]["width"]
            
            if val > 0.8:
                # Huge 'Ah' or 'Oh'
                self.target["mouth"]["openness"] = 0.5
                self.target["mouth"]["width"] = base_width * 0.7 # Narrow O shape
                self.target["mouth"]["curve"] = 0.0
            elif val > 0.4:
                # Wide 'ee' or 'eh'
                self.target["mouth"]["openness"] = 0.2
                self.target["mouth"]["width"] = base_width * 1.3 # Wide stretch
                self.target["mouth"]["curve"] = 0.3 # Smile
            elif val > 0.1:
                # Small mumble
                self.target["mouth"]["openness"] = 0.08
                self.target["mouth"]["width"] = base_width * 0.9
                self.target["mouth"]["curve"] = 0.1
            else:
                # Closed (Consonants like M, P, B)
                self.target["mouth"]["openness"] = 0.0
                self.target["mouth"]["width"] = base_width * 1.1 # Lips stretched flat
                self.target["mouth"]["curve"] = 0.0

    # ─── Drawing ───

    def _draw_face(self, screen, bounce_y=0):
        """Draw all face elements (simple, no dirty rect tracking)."""
        cx = self.width // 2
        cy = self.height // 2 + bounce_y
        blink_open = self._get_blink_openness()

        # Left eye
        le = self.current["leftEye"]
        self._draw_eye(screen,
                       cx + int(le["x"] * self.width),
                       cy + int(le["y"] * self.height),
                       le["width"], le["height"],
                       le["openness"] * blink_open)

        # Right eye
        re = self.current["rightEye"]
        self._draw_eye(screen,
                       cx + int(re["x"] * self.width),
                       cy + int(re["y"] * self.height),
                       re["width"], re["height"],
                       re["openness"] * blink_open)

        # Mouth
        self._draw_mouth(screen, cx, cy)

    def _draw_face_dirty(self, screen, bounce_y=0):
        """Draw face elements and return list of dirty rects."""
        cx = self.width // 2
        cy = self.height // 2 + bounce_y
        blink_open = self._get_blink_openness()
        dirty = []

        # Left eye
        le = self.current["leftEye"]
        r = self._draw_eye(screen,
                           cx + int(le["x"] * self.width),
                           cy + int(le["y"] * self.height),
                           le["width"], le["height"],
                           le["openness"] * blink_open)
        if r: dirty.append(r)

        # Right eye
        re = self.current["rightEye"]
        r = self._draw_eye(screen,
                           cx + int(re["x"] * self.width),
                           cy + int(re["y"] * self.height),
                           re["width"], re["height"],
                           re["openness"] * blink_open)
        if r: dirty.append(r)

        # Mouth
        r = self._draw_mouth(screen, cx, cy)
        if r: dirty.append(r)

        return dirty

    def _draw_eye(self, screen, cx, cy, w, h, openness):
        abs_w = max(int(w * self.width), 1)
        abs_h = max(int(h * self.height * openness), 1)

        if openness < 0.05:
            # Closed eye — horizontal line
            lw = max(int(abs_w * 0.8), 2)
            pygame.draw.line(screen, BLACK,
                             (cx - lw, cy), (cx + lw, cy), 4)
            return pygame.Rect(cx - lw, cy - 2, lw * 2, 5)

        # Filled ellipse
        rect = pygame.Rect(cx - abs_w, cy - abs_h, abs_w * 2, abs_h * 2)
        pygame.draw.ellipse(screen, BLACK, rect)
        return rect

    def _draw_mouth(self, screen, cx, cy):
        m = self.current["mouth"]
        mx = cx + int(m.get("offsetX", 0) * self.width)
        my = cy + int(m["y"] * self.height)
        abs_w = max(int(m["width"] * self.width), 2)
        style = m.get("style", "arc")

        if style == "arc":
            return self._draw_mouth_arc(screen, mx, my, abs_w, m["curve"], m["openness"])
        elif style == "open":
            return self._draw_mouth_open(screen, mx, my, abs_w, m["openness"])
        elif style == "zigzag":
            return self._draw_mouth_zigzag(screen, mx, my, abs_w)
        return None

    def _draw_mouth_arc(self, screen, cx, cy, abs_w, curve, openness):
        abs_curve = curve * self.height * 0.3

        if openness > 0.05:
            abs_open = openness * self.height * 0.06
            top_pts = _quadratic_bezier(
                (cx - abs_w, cy),
                (cx, cy + abs_curve),
                (cx + abs_w, cy)
            )
            bottom_pts = _quadratic_bezier(
                (cx + abs_w, cy),
                (cx, cy + abs_curve + abs_open),
                (cx - abs_w, cy)
            )
            polygon = top_pts + bottom_pts
            if len(polygon) >= 3:
                pygame.draw.polygon(screen, BLACK, polygon)
        else:
            pts = _quadratic_bezier(
                (cx - abs_w, cy),
                (cx, cy + abs_curve),
                (cx + abs_w, cy)
            )
            if len(pts) >= 2:
                pygame.draw.lines(screen, BLACK, False, pts, 4)

        # Return bounding rect (generous padding)
        h = int(abs(abs_curve) + openness * self.height * 0.06) + 8
        return pygame.Rect(cx - abs_w - 4, cy - 4, abs_w * 2 + 8, h + 8)

    def _draw_mouth_open(self, screen, cx, cy, abs_w, openness):
        """Round open mouth (surprised / speaking)."""
        abs_h = max(int(openness * self.height * 0.06), int(abs_w * 0.3))
        rect = pygame.Rect(cx - abs_w, cy - abs_h, abs_w * 2, abs_h * 2)
        pygame.draw.ellipse(screen, BLACK, rect)
        return rect

    def _draw_mouth_zigzag(self, screen, cx, cy, abs_w):
        """Zigzag mouth (error/confused)."""
        segments = 5
        seg_w = (abs_w * 2) / segments
        amp = int(self.height * 0.012)

        points = [(cx - abs_w, cy)]
        for i in range(1, segments + 1):
            x = cx - abs_w + int(seg_w * i)
            y = cy + (-amp if i % 2 == 0 else amp)
            points.append((x, y))

        if len(points) >= 2:
            pygame.draw.lines(screen, BLACK, False, points, 3)

        return pygame.Rect(cx - abs_w - 2, cy - amp - 2, abs_w * 2 + 4, amp * 2 + 4)
