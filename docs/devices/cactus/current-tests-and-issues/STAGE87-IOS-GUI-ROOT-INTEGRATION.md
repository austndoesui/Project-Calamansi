# Stage 87 — iOS root integration and GUI console handoff (2026-11-08)

## Scope and evidence

Stage 86's physical test established XNU, HFS+ on md0, Apple's `launchd`
executable activation and a genuine PID 1 SVC64/getpid syscall. It did not
establish that Apple's launchd completed service initialization or started
SpringBoard. Stage 87 keeps the exact same Stage 85 XNU kernel and native
handoff layout while combining the most useful safe root and display changes.

The 16 MiB RAMDisk now includes `/dev`, `/private/etc`, `/private/var`,
`/private/var/tmp`, `/private/var/run`, `/private/var/db`, `/Library/Preferences`,
`/System/Library/xpc`, and `/System/Library/Caches/com.apple.dyld`. It uses
the donor-style symlinks `/etc -> private/etc`, `/var -> private/var`, and
`/tmp -> private/var/tmp`, and contains iPhone 8 iOS 16.7.16 Apple's real
`launchd.plist` and `SystemVersion.plist`. This removes the known absent
`/dev` mount point that coincided with Stage 86's devfs ENOENT. The kernel
must still be checked on hardware for a successful devfs mount.

Boot arguments: `debug=0xc rd=md0 unentitled_ios_sim_launch=1 sweetfb_noconsole=1`.
The Stage85-development XNU binary contains `sweetfb_noconsole`. The existing
AppleCLCD code mutes kernel console drawing when the first GUI swap/present
occurs, allowing genuine graphical scanout to take over. This is not a
transparent alpha overlay, and it does **not** manufacture an Apple logo.
The framebuffer remains useful before the first GUI presentation; its native
console and panic handling are unchanged until then.

## Artifacts and checks

- Native kernel `kernel.development.cactus`: SHA256
  `dd39a64cd43de54dd79a2eaabb23b3e689a242179baccdf6399c93aad1da13fc`
  (the exact hardware-proven Stage85 kernel).
- Root `_build/ios16-runtime/stage87-guestfs.hfs`: 16,777,216 bytes;
  SHA256 `cf281dccb5b69add3ef01070a3ed21202287727dffa982772fd705ff4acaeea9`.
- Boot image `shim/out/cactus/cactus-trace-stage-87-boot.img`: 62,283,776 bytes;
  SHA256 `1d7ff3488ef38638deee017c86e87a75bfef4c494e3c968aafbff2f69c37f149`.
- Offline checks: exact 41 native instruction pins, entry address, ADT,
  ramdisk bytes, 16 KiB layout alignment, `boot_args` at `0x834bc000`,
  exact command line, image boot header, SHA256 manifest and patch sequence.
- `tools/stage87_prepare_root.py` creates a fresh image without modifying the
  donor or baseline, requires pinned Stage86 HFS SHA256 and genuine mounted
  Apple OS plists, and refuses to overwrite an existing output. An independent
  output reconstruction was validated using read-only guestfish directory
  and file inspection. The HFS metadata timestamp changes between builds,
  so each output is SHA-checked at pack and flash time, not expected to have
  an identical SHA256 on every reconstruction.

## Full dyld runtime: blocker and implementation route

The actual iPhone 8 iOS 16.7.16 SystemOS cryptex was mounted read-only by
APFS-FUSE at `/home/lapdq/calamansi-mount/systemos/root`. Its genuine dyld
cache is split into numerous `dyld_shared_cache_arm64*` files, some exceeding
100 MiB individually. The OS root and SystemOS cryptex apparent sizes are
approximately 7.79 GB and 3.36 GB. They cannot fit this 16 MiB boot RAMDisk
or a 64 MiB boot partition. Existing `tools/mkiosroot.sh` builds a complete
HFS+ iOS root from OS/SystemOS/AppOS volumes for storage-backed use.

The existing SWEET storage code is designed for Qualcomm UFS and cannot
drive cactus MediaTek eMMC. Relevant donor eMMC code is the Benesse project's
`bsd/dev/a04br3_msdc.c`, but it targets MT8167 and has board-specific
clock, pad, MMIO, DMA and partition assumptions. The next combined work item
is a **read-only MT6765 MSDC block driver and filesystem root path**, with
board-specific controller mapping checked against the cactus kernel/device
tree, read verification, and GPT/bounds checks before any full-root flash.
The available MT6765 Linux 4.19 DTS at
`/home/lapdq/cactus-kernel/src/kernel_oppo_4.19r/arch/arm64/boot/dts/mediatek/mt6765.dts`
reports **MSDC0 `0x11230000` (64 KiB)** and **MSDC1 `0x11240000`
(64 KiB)**, matching the nominal MSDC0 base of the Benesse MT8167 code.
The controller-base match alone cannot establish compatible clocks,
inherited register state, eMMC access or correct GPT partition selection;
all remain unverified on the Redmi 6A.
Never write a full-root image to `userdata` without explicit authorization:
doing so would replace the existing userdata filesystem. The user's existing
TWRP/Android partitions are left alone in this Stage87 test.

The `shared_region vm_map_enter ... error 0x4` remains an unresolved mapping
diagnostic. Providing the genuine dyld caches and observing loader execution
with a storage-backed root is required to determine its effect. Simply adding
empty cache directories will not make dyld ready or boot SpringBoard.

## Hardware test

The boot image was flashed after fastboot identity `product: cactus`, serial
`3184a8a17d2b`, image hash and size verification. The USB watcher was started
before `fastboot flash boot` and reboot. Both fastboot operations returned
`OKAY`. Capture:
`_build/stage87-hardware-captures/stage-cactus-20261108-114338-060/session-001-114350-670.bin`.
The decoder found 4,368 bytes, 78 valid frames, zero corrupt frames and
13 missing sequence numbers, including `0x2800` (pinned kernel identity) and
`0x3500` (**native XNU handoff**). This confirms a new Stage87 XNU handoff.
The device's framebuffer, devfs mount and PID 1 progress require the next
physical observation: the USB shim trace does not establish that those
post-handoff paths succeeded.

## Offline full-root build feasibility

All three actual donor APFS volumes are available: `os.dmg`, `systemos.dmg`
and `appos.dmg`; AppOS extracted from the pinned IPSW with SHA256
`391f2df322c3172b021b2874f6da5c3e78b70b3df8f502e1a4af2b1d715c4608`.
APFS-FUSE mounts succeeded read-only; the full-root builder
`tools/mkiosroot.sh` requires adaptation for this WSL environment because
the host kernel has no native HFS+ mount module. A userspace `guestmount`
with `-m /dev/sda:/:force` was independently validated writable, and an
adapted builder started an OS root copy, but per-file FUSE-to-FUSE `rsync`
through guestmount proved too slow for the complete multi-gigabyte tree.
That run was stopped, its temporary mounts unmounted and incomplete output
files removed. No full-root HFS image is yet available. The next efficient
host implementation should stream filesystem data in bulk through
libguestfs (`tar-in` or equivalent) or build on a host with HFS+ writable
mount support. The underlying eMMC driver is required regardless.

An isolated `tar-in /dev/stdin` smoke test succeeded, including extraction
of Apple's actual `launchd.plist` inside a temporary HFS image. A full OS
tar stream subsequently encountered **APFS-FUSE `Input/output error` and
`Transport endpoint is not connected`** while reading many donor binaries,
so it also failed to produce an acceptable full root. This failure was not
reported as success; the incomplete 16 GiB output and both sets of temporary
mounts were cleaned. The donor DMG files remain unchanged. A reliable APFS
reader or extraction/verification pass is now required before streaming a
complete OS image. Filling the boot RAMDisk with a partial cache would not
resolve these failures.
