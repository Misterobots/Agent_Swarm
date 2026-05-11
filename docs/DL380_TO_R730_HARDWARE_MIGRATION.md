# DL380 Gen9 → R730 Hardware Migration Runbook

**Goal**: Move CPUs, RAM, drives, and the 3070 Ti from the HPE DL380 Gen9 (`shivelyserver`, "Turing") into a Dell PowerEdge R730 so the GPU fits and the box gains compute (12C/24T → 20C/40T).

**Source**: HPE DL380 Gen9 — 2x Xeon E5-2630 v4 (10C/20T, 85W each), HPE Smart Array P440ar, 1x 500GB SATA boot, 3x 12TB SAS, 2x 450GB SAS unassigned.

**Target**: Dell R730 — currently 2x E5-2620 v3, PERC H730. Will receive: the v4 CPUs, the DL380's RAM, the 3070 Ti, and the data drives (in Dell caddies).

**Strategy**: Use the empty 12TB drive (`sdb` / `/mnt/vault`, currently 32K used) as a network-replication buffer so services keep running on the DL380 until the final cutover. Total real data to move: ~7.5TB.

---

## Hardware compatibility summary

| Item | Source | Target | Notes |
|---|---|---|---|
| CPUs | E5-2630 v4 (Broadwell-EP, 85W) | LGA2011-3 socket | R730 supports v4 with BIOS ≥ 2.0.1 |
| Heatsinks | HPE-specific | **Dell R730 standard heatsinks required** | ~$15-25/ea on eBay; HPE heatsinks won't mount |
| RAM | DDR4 RDIMM | R730 DDR4 RDIMM slots | Will run; iDRAC may log "non-Dell DIMM" warnings (cosmetic) |
| Drives | HPE caddies | **Dell R730 caddies required** | ~$5-10/ea on eBay |
| RAID metadata | HPE Smart Array DDF | PERC H730 | **Not portable** — drives must be wiped or set to HBA mode + reformatted |
| GPU | RTX 3070 Ti (didn't fit DL380) | R730 riser 2 (x16) | Needs **GPU enablement kit**: riser cage + dual-CPU power cable |

**Critical pre-check**: confirm R730 has the GPU power cable (small connector near the riser cage labeled "GPU"). Without it, the 3070 Ti has no power.

---

## Phase 0 — Inventory and backup (do this first, no time pressure)

### 0.1 Inventory snapshot
On `shivelyserver`:
```bash
# Create the migration directory first
mkdir -p ~/migration

# Hardware
sudo dmidecode -t system,bios,memory > ~/migration/hw_inventory.txt
sudo ssacli ctrl all show config detail >> ~/migration/hw_inventory.txt

# Storage
lsblk -o NAME,SIZE,FSTYPE,UUID,MOUNTPOINT,LABEL > ~/migration/storage.txt
df -h >> ~/migration/storage.txt
sudo blkid >> ~/migration/storage.txt
cat /etc/fstab >> ~/migration/storage.txt

# Services
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' > ~/migration/containers.txt
sudo systemctl list-units --type=service --state=running > ~/migration/services.txt

# Network
ip a > ~/migration/network.txt
ls /etc/netplan/ >> ~/migration/network.txt
sudo cat /etc/netplan/*.yaml >> ~/migration/network.txt 2>/dev/null

# User state
cp -r ~/.ssh ~/migration/ssh_backup
cp /etc/hostname /etc/hosts ~/migration/
```

Save `~/migration/` somewhere off-box (push to git, copy to Lovelace, USB stick — at least two places).

### 0.2 Backup configs and state
```bash
# Saltbox + compose
sudo tar czf ~/migration/saltbox_opt.tgz /opt/

# Docker volumes (named volumes only — bind mounts already on disk)
sudo tar czf ~/migration/docker_volumes.tgz /var/lib/docker/volumes/

# Postgres dumps (do this for every postgres container)
docker ps --format '{{.Names}}' | grep -i postgres | while read c; do
  docker exec "$c" pg_dumpall -U postgres > ~/migration/${c}_dump.sql
done

# Home dir essentials
tar czf ~/migration/home.tgz ~/.config ~/.docker ~/dotfiles 2>/dev/null
```

**Verify the backups before you trust them.** Untar one to a scratch dir and spot-check files.

### 0.3 Snapshot DNS / reverse proxy
- Export Cloudflare DNS records for `shivelymedia.com` (CSV from dashboard)
- Snapshot Traefik dynamic config: `cp -r /opt/traefik ~/migration/traefik_snapshot`
- List Tailscale node names if applicable: `tailscale status > ~/migration/tailscale.txt`

---

## Phase 1 — Pre-stage R730 (before hardware swap, while DL380 still serves traffic)

### 1.1 R730 BIOS update (mandatory for v4 CPUs)
1. Connect to R730 iDRAC → Maintenance → Lifecycle Controller → Firmware Update.
2. Update BIOS to **2.0.1 or newer** (latest is fine, currently 2.19.0).
3. Reboot, confirm version.

> Do this **while the v3 CPUs are still in** — if you wait until after the swap, an old BIOS won't POST with v4 CPUs and you'll be stuck.

### 1.2 PERC H730 mode decision
Two valid options:

**Option A — HBA / pass-through mode** (recommended for ZFS, mergerfs, mdadm setups)
- iDRAC → Storage → Controllers → PERC H730 → Convert to HBA Mode
- Drives appear as raw devices, no PERC metadata layer
- Matches the spirit of your current "single-disk RAID 0" workaround

**Option B — Stay in RAID mode, create single-disk RAID 0s** (matches current DL380 setup exactly)
- For each drive, create a 1-disk RAID 0 in iDRAC
- More familiar; same caveats you have today

Pick A unless you have a reason. The runbook below assumes A.

### 1.3 Move the empty 12TB (`sdb`) into the R730 first
On DL380:
```bash
# Confirm empty
df -h /mnt/vault          # should be ~32K used
sudo umount /mnt/vault
sudo sed -i.bak '\|/mnt/vault|d' /etc/fstab    # remove from fstab
```
Mark it removed in the HPE controller:
```bash
sudo ssacli ctrl slot=0 ld 2 delete forced     # adjust ld# to match Array B
```
Power down DL380, pull the drive, transfer to a Dell caddy, install in R730 bay 0.

### 1.4 Install OS on R730
- Use one of the **2x 450GB SAS unassigned** drives as boot (or both in RAID 1 if you want mirrored boot).
- Pull them from the DL380 (they're unassigned, no data), wipe, install in R730 bays 1-2.
- Boot Ubuntu Server installer (match shivelyserver's version: `lsb_release -a` on DL380 first).
- Hostname: pick **staging name** for now (e.g., `shivelyserver-r730`). Final rename happens at cutover.
- Static IP on a different address than `shivelyserver` so both can run side-by-side.

### 1.5 Install software stack on R730
```bash
# Match the source environment
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl rsync git htop iotop iperf3

# Docker (match DL380's docker version — check with `docker --version` on DL380 first)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# NVIDIA driver + container toolkit (drivers stay inert until GPU is installed)
sudo apt install -y nvidia-driver-550 nvidia-container-toolkit
sudo systemctl restart docker

# Saltbox prereqs (per Saltbox docs — runs Ansible to bootstrap)
# Do not run `sb install` for media services yet — wait until after data is on box
```

### 1.6 Format and mount the 12TB buffer drive on R730
```bash
# Wipe HPE DDF metadata
sudo wipefs -a /dev/sdX           # sdX = the 12TB you moved
sudo sgdisk --zap-all /dev/sdX

# Format ext4 (or xfs if you prefer parity with sdc/sdd)
sudo mkfs.ext4 -L migration_buffer /dev/sdX
sudo mkdir -p /mnt/buffer
echo "LABEL=migration_buffer /mnt/buffer ext4 defaults 0 2" | sudo tee -a /etc/fstab
sudo mount /mnt/buffer
df -h /mnt/buffer
```

### 1.7 Network speed test
```bash
# On R730:
iperf3 -s

# On DL380:
iperf3 -c <r730-ip> -t 30
```
Record the speed. Gigabit ≈ 110 MB/s actual ≈ 17h for 7.2TB. 10GbE ≈ 1+ GB/s ≈ 2h.

---

## Phase 2 — Replicate data over the network (DL380 still serving)

### 2.1 First-pass rsync (services running)
Run from R730 to pull from DL380 — easier on resources than pushing.

```bash
# On R730 — run inside tmux/screen, this takes hours
tmux new -s migrate

# Media drives
sudo mkdir -p /mnt/buffer/disk1 /mnt/buffer/disk2 /mnt/buffer/saltbox

sudo rsync -aHAX --info=progress2 --partial \
    --exclude='lost+found' \
    misterobots@<dl380-ip>:/mnt/disks/disk1/ /mnt/buffer/disk1/ \
    2>&1 | tee ~/migration/rsync_disk1_pass1.log

sudo rsync -aHAX --info=progress2 --partial \
    --exclude='lost+found' \
    misterobots@<dl380-ip>:/mnt/disks/disk2/ /mnt/buffer/disk2/ \
    2>&1 | tee ~/migration/rsync_disk2_pass1.log

# Saltbox + agent_runtime data (root-owned — needs sudo over ssh)
sudo rsync -aHAX --info=progress2 --partial \
    --rsync-path="sudo rsync" \
    misterobots@<dl380-ip>:/opt/ /mnt/buffer/saltbox/opt/ \
    2>&1 | tee ~/migration/rsync_opt_pass1.log
```

Flags explained:
- `-a` archive (preserves perms, times, symlinks, owner/group, etc.)
- `-H` preserve hardlinks (mergerfs uses these)
- `-A` preserve ACLs
- `-X` preserve xattrs
- `--partial` resume on interrupt
- `--info=progress2` overall progress, not per-file

### 2.2 Stage Saltbox / agent_runtime configs
On R730:
```bash
# Pull the backup tarballs you made in Phase 0
scp misterobots@<dl380-ip>:~/migration/*.tgz ~/migration/
scp misterobots@<dl380-ip>:~/migration/*.sql ~/migration/

# Don't extract /opt yet — wait until cutover so Saltbox state matches final state
```

### 2.3 Smoke-test agent_runtime on R730 staging
- Bring up agent_runtime via compose pointed at `/mnt/buffer/saltbox/opt/agent_runtime`
- Use a different port / staging hostname so it doesn't fight the DL380 instance
- Confirm `/health` responds, DB migrations complete, basic API works
- Don't run training jobs yet — GPU isn't installed

---

## Phase 3 — Cutover (the actual swap day)

**Total expected time**: 3–5 hours. Schedule it. Tell the team.

### 3.1 Pre-cutover
- [ ] Final backup of `/opt`, postgres dumps, anything that changed since Phase 0
- [ ] Stop services on DL380: `cd /opt && docker compose down` (or `sb stop`)
- [ ] Final delta rsync (same commands as 2.1, will be quick — only changed bytes)
- [ ] Stop services on R730 staging
- [ ] Verify DL380 is idle: `docker ps` empty, no Saltbox processes

### 3.2 Hardware swap
- [ ] Power down both servers, unplug power cables
- [ ] Pull RAM from DL380 → install in R730 (note DIMM slot map: A1/B1/C1/D1 first per CPU for full bandwidth)
- [ ] Pull v3 CPUs from R730, set aside (resale value)
- [ ] Pull v4 CPUs from DL380, install in R730 with **Dell heatsinks** (not HPE)
- [ ] Install RTX 3070 Ti in R730 riser 2, connect GPU power cable
- [ ] Pull `sdc` and `sdd` (12TB media drives) from DL380, wipe HPE metadata if needed, install in Dell caddies, install in R730
- [ ] Cable check: power, network, iDRAC

### 3.3 First boot
- [ ] Power on, enter BIOS
- [ ] Verify: 2x E5-2630 v4 detected, all RAM visible, GPU detected
- [ ] Boot to OS
- [ ] `nvidia-smi` shows the 3070 Ti
- [ ] `lsblk` shows all drives (boot + buffer + 2x media)

### 3.4 Mount media drives
```bash
# sdc and sdd were XFS — mount by UUID (already in fstab snapshot from Phase 0)
sudo blkid /dev/sdX /dev/sdY    # find new device names
sudo mkdir -p /mnt/disks/disk1 /mnt/disks/disk2

# Add UUIDs to /etc/fstab matching the originals
sudo nano /etc/fstab

sudo mount -a
df -h | grep disks
```

### 3.5 Reattach mergerfs
- Restore mergerfs config from `/mnt/buffer/saltbox/opt/...` (path depends on Saltbox layout — confirm during Phase 1)
- Mount the union, verify `/mnt/unionfs` shows ~7.2TB across disks

### 3.6 Restore services
```bash
# Move Saltbox state into place
sudo rsync -aHAX /mnt/buffer/saltbox/opt/ /opt/

# Restore postgres
docker compose up -d postgres
cat ~/migration/<container>_dump.sql | docker exec -i <postgres-container> psql -U postgres

# Bring up the rest
sb start    # or `docker compose up -d` per stack
```

### 3.7 Identity flip
- [ ] `sudo hostnamectl set-hostname shivelyserver`
- [ ] Update static IP to match DL380's old IP, OR update DNS to point to R730's IP
- [ ] Update `/etc/hosts` if any services hardcode the hostname
- [ ] Restart Tailscale if applicable: `sudo tailscale up --hostname=shivelyserver`
- [ ] Cloudflare: confirm `hive.shivelymedia.com` and any other records point to the right IP

### 3.8 Verification
- [ ] `nvidia-smi` works under Docker: `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi`
- [ ] All Saltbox services healthy: `docker ps`, check Mission Control
- [ ] Media playback works (test Plex/Jellyfin)
- [ ] agent_runtime `/health` and a real training preflight returns clean
- [ ] Lovelace can reach R730 on the expected hostname/IP

### 3.9 Post-cutover
- [ ] Keep DL380 powered off but intact for 1–2 weeks (rollback option)
- [ ] After confidence period: wipe DL380 drives, decommission or repurpose
- [ ] Update `docs/INFRASTRUCTURE_REFERENCE.md` with new hardware spec

---

## Rollback plan

If R730 fails to boot or services don't come up:

1. Power off R730
2. Move `sdc` and `sdd` back into HPE caddies, reinstall in DL380
3. Move CPUs back to DL380 (reverse heatsink swap)
4. DL380 boots normally — buffer drive (sdb) is now blank/missing but other services unaffected
5. Diagnose R730 issue at leisure

This is why we keep DL380 powered off but assembled until confidence period passes.

---

## Appendix — Useful commands during migration

```bash
# Watch rsync progress in another tmux pane
watch -n 10 'df -h /mnt/buffer'

# Monitor network throughput
sudo iftop -i eno1

# Check rsync ETA
ls -la ~/migration/rsync_*.log

# Verify checksums after rsync (slow but definitive)
sudo rsync -aHAXn --checksum \
    misterobots@<dl380-ip>:/mnt/disks/disk1/ /mnt/buffer/disk1/ \
    | head -50    # any output = mismatched files

# Quick filesystem health
sudo xfs_repair -n /dev/sdc       # dry run
sudo e2fsck -n /dev/sdb           # dry run
```
