# Memex Brain — rack display kiosk

An ambient "thinking brain" animation for the monitor in the rack: the Memex
hexagonal logo rendered as a living neural graph (signals firing along the
edges, nodes lighting as thoughts arrive, a thought-wave rippling out from the
hub) suspended in a slow-drifting amber nebula. It's a **deterministic, seamless
22-second loop** — no GPU telemetry, no live inference hooks. It runs as a
fullscreen video on Turing's HDMI output (NVIDIA RTX 3070 Ti), and a key combo
swaps to a login terminal.

## Files

| File | Purpose |
|------|---------|
| `memex_brain.html` | The animation. One file, two modes: open bare in a browser → live preview; pass `?frame=K&total=N&w=W&h=H` → renders one deterministic frame (used by the renderer). |
| `render.mjs` | Headless Playwright renderer — captures 660 frames (30 fps × 22 s). |
| `memex_brain_portrait.webm` | Pre-rendered loop, **1440×2560 portrait**, VP8. This is what plays on the monitor. |

## Display facts (Turing)

- The monitor is mounted **portrait** on its stand; the HDMI signal is still
  landscape, so the output is rotated 90° at display time (see below).
- The rack door is **tinted acrylic**, which dims everything behind it. The
  animation is brightened to compensate via `GAIN` (top of `memex_brain.html`,
  currently `1.45`). Raise it if the display looks dim through the door, lower
  it toward `1.0` for clear glass.
- Turing draws its console on the onboard **Matrox G200** by default; the NVIDIA
  HDMI output needs KMS enabled (`nvidia-drm.modeset=1`) to drive a display.

## Deploy on Turing

### 1. Put the asset in place
```bash
sudo mkdir -p /opt/kiosk
sudo cp memex_brain_portrait.webm /opt/kiosk/
sudo apt install -y mpv
```

### 2. Enable NVIDIA KMS + route the console to the HDMI output, rotated
Append to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`:
```
nvidia-drm.modeset=1 fbcon=map:1 fbcon=rotate:1
```
- `nvidia-drm.modeset=1` — lets the 3070 Ti drive the HDMI display.
- `fbcon=map:1` — puts the text console on the NVIDIA framebuffer (verify with
  `cat /proc/fb`; if `nvidia-drmfb` is fb0, use `map:0`).
- `fbcon=rotate:1` — rotates the **terminal** 90° CW for the portrait panel
  (use `rotate:3` for CCW if it comes out upside-down).
```bash
echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-drm.conf
sudo update-grub && sudo update-initramfs -u
sudo reboot
```
Verify after reboot:
```bash
cat /sys/module/nvidia_drm/parameters/modeset            # → Y
for d in /dev/dri/card*; do n=${d##*/}; echo "$n $(cat /sys/class/drm/$n/device/vendor)"; done
# vendor 0x10de = NVIDIA — note that card node (likely card1)
```

### 3. Animation on boot, terminal on a key combo
Autologin tty1 → plays the loop (rotated to match the panel); tty2 stays a
normal login.
```bash
sudo useradd -m -G video,render kiosk 2>/dev/null || sudo usermod -aG video,render kiosk

sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf >/dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin kiosk --noclear %I $TERM
EOF

sudo tee /home/kiosk/.bash_profile >/dev/null <<'EOF'
if [ "$(tty)" = "/dev/tty1" ]; then
  exec mpv --really-quiet --no-config --fs --loop-file=inf --no-audio \
    --no-input-default-bindings --cursor-autohide=always \
    --gpu-context=drm --drm-connector=HDMI-A-1 --drm-device=/dev/dri/card1 \
    --video-rotate=90 \
    /opt/kiosk/memex_brain_portrait.webm
fi
EOF
sudo chown kiosk:kiosk /home/kiosk/.bash_profile

sudo systemctl daemon-reload
sudo systemctl restart getty@tty1
```
- Set `--drm-device=` to the NVIDIA card node from step 2 (omit if it's the only
  KMS device).
- `--video-rotate=90` matches `fbcon=rotate:1`; use `270` with `rotate:3`.

### Behavior
- **Boot →** animation fullscreen on the portrait monitor, looping forever.
- **Ctrl+Alt+F2 →** login terminal (upright, same monitor).
- **Ctrl+Alt+F1 →** back to the animation.

Ollama is untouched — VP8 decodes on CPU (trivial for a 22 s loop); the GPU's
compute stays free for inference.

## Regenerate / tweak the loop

Edit `memex_brain.html` (colors, `GAIN`, nebula density, signal speeds — all at
the top of the script), then:
```bash
npm install playwright          # PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 if Chromium already present
# CHROME_PATH=/path/to/chrome   # optional: reuse an existing Chromium
node render.mjs                 # writes frames/f0000.jpg … (1440×2560, 660 frames)

# encode a seamless VP8 loop (any ffmpeg with libvpx works):
cat $(ls frames/f*.jpg | sort) | ffmpeg -f image2pipe -vcodec mjpeg -framerate 30 -i pipe:0 \
  -c:v libvpx -b:v 14M -crf 8 -pix_fmt yuv420p -auto-alt-ref 0 memex_brain_portrait.webm
```
Change `W`/`H` in `render.mjs` for a different resolution (e.g. `2160×3840` for a
4K portrait panel). The loop stays seamless because every animated term is a
whole-number multiple of the loop phase.
