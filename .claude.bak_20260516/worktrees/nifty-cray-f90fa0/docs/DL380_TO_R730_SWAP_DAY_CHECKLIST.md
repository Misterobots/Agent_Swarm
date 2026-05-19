# DL380 → R730 Swap Day Checklist

**Print this. Have it next to you.** Cross items off in pen.

Companion to: `DL380_TO_R730_HARDWARE_MIGRATION.md` (full runbook with commands).

---

## Before swap day — shopping list

- [ ] 2x Dell R730 standard heatsinks (≤120W, e.g., Dell PN 412-AAFT)
- [ ] 4-8x Dell R730 drive caddies (3.5" LFF for 12TB SAS, 2.5" SFF for 450GB if applicable)
- [ ] Thermal paste (Arctic MX-4 or equivalent)
- [ ] Anti-static wrist strap
- [ ] R730 GPU enablement kit (riser cage + GPU power cable) — **verify R730 already has this**
- [ ] USB stick with Ubuntu Server installer (match DL380's version)
- [ ] Notebook + pen for serial numbers / DIMM positions

---

## T-7 days — Inventory and first backup

- [ ] Run inventory commands from runbook §0.1, save to `~/migration/`
- [ ] Run backup commands from runbook §0.2
- [ ] Postgres dumps from every container (§0.2)
- [ ] **Verify a backup restores** — untar one to scratch, spot-check
- [ ] Push `~/migration/` to a second location (git, Lovelace, USB)
- [ ] Snapshot Cloudflare DNS, Traefik config, Tailscale list (§0.3)

---

## T-3 days — Pre-stage R730

- [ ] R730 BIOS updated to ≥ 2.0.1 (**before any CPU swap**)
- [ ] PERC H730 set to HBA mode (or decision to stay RAID documented)
- [ ] On DL380: unmount `/mnt/vault`, remove from fstab, delete logical drive
- [ ] Pull empty 12TB from DL380, install in R730 (Dell caddy)
- [ ] Pull 1-2x 450GB unassigned from DL380, install in R730 as boot
- [ ] Install Ubuntu Server on R730 (staging hostname, different IP)
- [ ] Install Docker, NVIDIA stack, Saltbox prereqs (§1.5)
- [ ] Format 12TB as `/mnt/buffer` (§1.6)
- [ ] `iperf3` between DL380 and R730 — record speed

---

## T-2 days — Replicate data

- [ ] tmux session opened, rsync `disk1` running (§2.1)
- [ ] After disk1 done: rsync `disk2`
- [ ] rsync `/opt` (Saltbox) — last
- [ ] Pull backup tarballs and SQL dumps to R730
- [ ] Stage agent_runtime on R730, smoke-test `/health` endpoint
- [ ] Note any errors / files that didn't transfer

---

## T-1 day — Final prep

- [ ] Re-run inventory snapshot on DL380 (capture last-day changes)
- [ ] Confirm R730 GPU power cable present and reachable to riser 2
- [ ] Confirm Dell heatsinks and caddies have arrived
- [ ] Block out 4-6 hours on calendar for swap day
- [ ] Tell anyone who depends on the services (team of 3)
- [ ] Charge phone, have flashlight, clear workspace

---

## Swap day — T-0

### Stage 1: Final sync (30 min)

- [ ] Stop services on DL380: `cd /opt && docker compose down` (or `sb stop`)
- [ ] Final delta rsync from DL380 → R730 buffer (same commands as Phase 2)
- [ ] Stop services on R730 staging
- [ ] Verify DL380 idle (`docker ps` empty)

### Stage 2: Power down (5 min)

- [ ] Power down DL380 cleanly: `sudo shutdown -h now`
- [ ] Power down R730 cleanly
- [ ] **Unplug both power cables** (CPUs share standby power on these boards)
- [ ] Anti-static strap on, attached to chassis

### Stage 3: Hardware swap (60-90 min)

**RAM**
- [ ] Pull DDR4 DIMMs from DL380, note slots
- [ ] Install in R730 — A1/B1/C1/D1 first per CPU (DIMM map in R730 manual)
- [ ] All slots populated correctly per Dell channel order

**CPUs**
- [ ] Pull v3 CPUs from R730, place in anti-static foam (resale)
- [ ] Pull v4 CPUs from DL380, **inspect socket pins** (a flashlight helps)
- [ ] Apply fresh thermal paste (pea-sized, center)
- [ ] Install v4s in R730 sockets — careful with retention frame, 2-lever Dell design
- [ ] Install **Dell heatsinks** (not HPE) — torque pattern: cross diagonal, even

**GPU**
- [ ] Install RTX 3070 Ti in R730 riser 2 (x16 slot)
- [ ] Connect GPU power cable from board GPU header
- [ ] Riser cage seated and screwed

**Drives**
- [ ] Pull `sdc` (MediaDrive1) from DL380, transfer to Dell caddy, install R730
- [ ] Pull `sdd` (MediaDrive2) from DL380, transfer to Dell caddy, install R730
- [ ] (Optional) wipe HPE metadata: `wipefs -a` after install on R730

**Cabling**
- [ ] Power, network (eno1 to your switch), iDRAC network
- [ ] Cable management — keep airflow paths clear

### Stage 4: First boot (15 min)

- [ ] Power on R730 → enter BIOS
- [ ] Verify in BIOS: 2x E5-2630 v4, full RAM total, GPU listed in PCIe devices
- [ ] Save & exit, boot to OS
- [ ] At login: `nvidia-smi` shows 3070 Ti
- [ ] `lsblk` shows boot + buffer + 2x 12TB media drives

### Stage 5: Mount and restore (60-90 min)

- [ ] `sudo blkid` — capture new UUIDs for sdc/sdd
- [ ] Update `/etc/fstab` with new UUIDs for `/mnt/disks/disk1` and `/mnt/disks/disk2`
- [ ] `sudo mount -a`, verify both 12TB drives mounted with original data
- [ ] Restore mergerfs config, mount union at `/mnt/unionfs`
- [ ] Move buffered Saltbox state into `/opt/` (rsync from `/mnt/buffer/saltbox/opt/`)
- [ ] Bring up postgres container, restore dumps
- [ ] `sb start` (or `docker compose up -d`)

### Stage 6: Identity flip (15 min)

- [ ] `sudo hostnamectl set-hostname shivelyserver`
- [ ] Static IP changed to DL380's old IP (OR Cloudflare DNS updated)
- [ ] Tailscale rejoined as `shivelyserver` if applicable
- [ ] `/etc/hosts` updated

### Stage 7: Verification (30 min)

- [ ] `docker ps` — all expected containers Up and healthy
- [ ] Mission Control loads at expected URL
- [ ] `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi` succeeds
- [ ] agent_runtime `/health` returns 200
- [ ] One training preflight (dry-run) returns clean — verifies GPU + dispatcher path
- [ ] Plex/Jellyfin (or whatever media app) plays a file from `/mnt/unionfs`
- [ ] Lovelace can reach R730 on expected hostname

### Stage 8: Stand down (15 min)

- [ ] DL380 stays **powered off but assembled** for 1-2 week rollback window
- [ ] Update `docs/INFRASTRUCTURE_REFERENCE.md` with new spec
- [ ] Commit migration notes to git
- [ ] Coffee. You earned it.

---

## Bail-out / rollback (if R730 won't boot or services don't come up)

1. [ ] Power off R730, unplug
2. [ ] Pull `sdc` + `sdd` from R730 (Dell caddies → HPE caddies)
3. [ ] Reinstall in DL380
4. [ ] Move v4 CPUs back to DL380 (reverse heatsink swap)
5. [ ] DL380 powers on, services resume from last good state
6. [ ] Diagnose R730 issue without time pressure

The 12TB buffer drive (`sdb`) stays in R730 — DL380 will boot fine without it (was empty anyway).

---

## Don't forget

- [ ] Dell PERC H730 BIOS / firmware also wants to be current — not just system BIOS
- [ ] iDRAC password — set it, write it down, don't lose it
- [ ] DL380 iLO can stay accessible during swap window for last-minute checks
- [ ] If you reuse the DL380 hostname, **clear the DHCP lease** on your router or you'll fight a phantom
- [ ] Backups are not safe until **verified by restore test**
