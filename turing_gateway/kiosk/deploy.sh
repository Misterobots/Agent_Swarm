#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Memex Brain kiosk deployer — run ON TURING with sudo.
#
#   sudo turing_gateway/kiosk/deploy.sh            # from a repo checkout on Turing
#   # …or copy this dir + the .webm to Turing and run it there.
#
# Idempotent: safe to re-run. To flip rotation if the image is upside-down:
#   sudo ROTATE_FBCON=3 ROTATE_MPV=270 turing_gateway/kiosk/deploy.sh
#
# A reboot is required at the end (for nvidia KMS + console rotation).
# RECOVERY: a monitor on the onboard Matrox VGA port always shows the console,
# even if the NVIDIA/HDMI settings are wrong — keep that option handy.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

KIOSK_DIR=/opt/kiosk
ASSET=memex_brain_portrait.webm
CONNECTOR=${CONNECTOR:-HDMI-A-1}     # NVIDIA HDMI connector (from drm status)
FBCON_MAP=${FBCON_MAP:-1}            # console framebuffer index (verify: cat /proc/fb)
ROTATE_FBCON=${ROTATE_FBCON:-1}      # terminal rotation: 1 = 90° CW, 3 = 90° CCW
ROTATE_MPV=${ROTATE_MPV:-90}         # video rotation: 90 (matches fbcon 1), 270 (matches 3)
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

[[ $EUID -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }

echo "==> Pre-flight"
command -v nvidia-smi >/dev/null && nvidia-smi -L || echo "  ! nvidia-smi not found — is the NVIDIA driver installed?"

echo "==> Installing mpv"
apt-get update -qq && apt-get install -y -qq mpv

echo "==> Placing animation in ${KIOSK_DIR}"
install -d "$KIOSK_DIR"
if [[ -f "$SRC_DIR/$ASSET" ]]; then
  install -m0644 "$SRC_DIR/$ASSET" "$KIOSK_DIR/$ASSET"
elif [[ -f "$KIOSK_DIR/$ASSET" ]]; then
  echo "  using existing $KIOSK_DIR/$ASSET"
else
  echo "  ! $ASSET not found next to this script or in $KIOSK_DIR — copy it there first." >&2
  exit 1
fi

echo "==> Enabling NVIDIA DRM modeset"
echo 'options nvidia-drm modeset=1' > /etc/modprobe.d/nvidia-drm.conf

echo "==> Updating GRUB kernel cmdline (backup: /etc/default/grub.memex.bak)"
cp -n /etc/default/grub /etc/default/grub.memex.bak
# strip any previously-managed tokens, then append fresh (keeps re-runs clean)
sed -i -E 's/ ?nvidia-drm\.modeset=[0-9]+//g; s/ ?fbcon=map:[0-9]+//g; s/ ?fbcon=rotate:[0-9]+//g' /etc/default/grub
sed -i "s/\(GRUB_CMDLINE_LINUX_DEFAULT=\"[^\"]*\)\"/\1 nvidia-drm.modeset=1 fbcon=map:${FBCON_MAP} fbcon=rotate:${ROTATE_FBCON}\"/" /etc/default/grub
echo "  cmdline now: $(grep GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub)"
update-grub
update-initramfs -u

echo "==> Creating kiosk user + tty1 autologin"
id kiosk &>/dev/null || useradd -m -s /bin/bash kiosk
usermod -s /bin/bash kiosk          # force bash so ~/.bash_profile is read (not dash/.profile)
usermod -aG video,render kiosk
install -d /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin kiosk --noclear %I \$TERM
EOF

echo "==> Writing kiosk launcher (auto-detects the NVIDIA card node at runtime)"
cat > /home/kiosk/.bash_profile <<EOF
if [ "\$(tty)" = "/dev/tty1" ]; then
  CARD=\$(for d in /dev/dri/card*; do n=\${d##*/}; \\
    [ "\$(cat /sys/class/drm/\$n/device/vendor 2>/dev/null)" = "0x10de" ] && echo "\$d" && break; done)
  echo "kiosk: launching mpv on \${CARD:-<no NVIDIA DRM card found>} (connector ${CONNECTOR})"
  mpv --no-config --fs --loop-file=inf --no-audio \\
    --no-input-default-bindings --cursor-autohide=always \\
    --gpu-context=drm --drm-connector=${CONNECTOR} \${CARD:+--drm-device=\$CARD} \\
    --video-rotate=${ROTATE_MPV} \\
    ${KIOSK_DIR}/${ASSET}
  echo "kiosk: mpv exited \$? — leaving you on a shell so the error is visible"
fi
EOF
chown kiosk:kiosk /home/kiosk/.bash_profile

systemctl daemon-reload

cat <<EOF

==> DONE.  Reboot to activate:   sudo reboot

After reboot:
  • Animation plays on the HDMI/portrait monitor at boot.
  • Ctrl+Alt+F2 → login terminal (upright) ; Ctrl+Alt+F1 → back to animation.

If the picture is upside-down / wrong rotation:
  sudo ROTATE_FBCON=3 ROTATE_MPV=270 $0   &&  sudo reboot
If the terminal lands on the Matrox VGA instead of HDMI, check 'cat /proc/fb'
and re-run with e.g.  sudo FBCON_MAP=0 $0
EOF
