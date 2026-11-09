# Stage 88 hardware storage proof and XNU integration (2026-11-08)

## Hardware baseline

Stage87's updated HFS root + genuine iOS launch configuration still showed
the Stage85-derived green `PID1 RUNNING` status on the Redmi 6A. This status
means PID 1 executed a getpid syscall; Apple's full launchd initialization,
UIKit and SpringBoard have not been verified.

Stage88 was **built and flashed** on the real cactus using the COM25 watcher
and then rebooted successfully. It added a pre-XNU read-only eMMC probe while
preserving the exact Stage87 HFS root and Stage85 XNU kernel. The USB trace
confirmed that MMC commands and a GPT CRC validation worked on this board.
The trace also confirmed that the native XNU handoff still completed.

## Capacity and runtime dependency evidence

- Read-only fastboot identity: `product: cactus`, serial `3184a8a17d2b`.
- Boot partition `0x4000000` = 64 MiB; current Stage87 image 62,283,776 B.
- System partition `0x280000000` = 10 GiB; userdata `0x438ffbe00`
  (~18.1 GiB), both currently occupied by device filesystems. No changes
  to either partition are authorized by this milestone.
- Genuine iOS 16.7.16 SystemOS cryptex dyld cache consists of **44** files,
  with **3,329,294,336 bytes (3.10 GiB)** combined, measured from mounted
  donor `System/Library/Caches/com.apple.dyld/`. This includes symbols and
  numerous `dyld_shared_cache_arm64.*` subcaches; many required segments are
  over 100 MiB. The cache is far larger than the 16 MiB RAMDisk or 64 MiB
  boot image. The `launchd` Mach-O audit also identifies actual dependencies
  `/usr/lib/libSystem.B.dylib` and `/usr/lib/libobjc.A.dylib`; SpringBoard
  requires Foundation and SpringBoard private framework in addition.
- Apple's loader and the pinned current XNU kernel were already placed in
  the ramdisk. The missing dependencies/cache were not supplied by Stage87.
  The earlier `shared_region vm_map_enter ... 0x4` error has not yet been
  isolated and may require a separate platform/VM fix even once the cache is
  accessible. Hardware drivers and iOS service infrastructure are further
  prerequisites for a usable SpringBoard GUI.

## Shortest viable route and decision

Full runtime assets must be accessible beyond the boot partition. The least
speculative path uses the current device's eMMC via a **read-only XNU MSDC
driver** and a suitable prepared root, with strict GPT bounds validation.
The Benesse MT8167 reference driver `a04br3_msdc.c` implements BSD disk and
GPT partition discovery, but its MSDC controller address is **0x11120000**.
The Redmi 6A MT6765 kernel DTS instead locates MSDC0 at **0x11230000**
and MSDC1 at `0x11240000`. Linux MT6765 register definitions agree with
the donor's MSDC register offsets; these are distinct SoC addresses.

Stage88 proved that inherited LK clock/card initialization is sufficient for
a bounded PIO read. The USB frame sequence from
`_build/stage88-msdc-readonly-captures/stage-cactus-20261108-121329-877/session-001-121339-265.bin`
contains **81 valid frames, 0 corrupt**, including:

- `0x8800`: MSDC0 physical controller `0x11230000` and register snapshot.
- `0x8801`: CMD13 success, R1 `0x900` (card ready/TRAN).
- `0x8802`: CMD17 read sector 1 success.
- `0x8803`: `EFI PART` header, expected/actual GPT CRC32 both
  `0x9f1ca5d9`.
- `0x8804`: GPT header advertises 128 entries of 128 bytes each.
- `0x880e`: original controller configuration restored.
- `0x2800` and `0x3500`: exact native XNU kernel identity and handoff.

Stage88 image:
`shim/out/cactus/cactus-trace-stage-88-boot.img`,
62,283,776 bytes, SHA256
`c4e5030e4b30f953d031789c1c3fe574abdb9720e29c06567615b01fffed7a1b`.

The next XNU driver patch is
`xnu/patches/devices/cactus/0121-cactus-msdc-readonly-root.patch`.
It supplies a Cactus-gated BSD read-only block/character driver, validated
GPT and an `iosroot` partition selection. It supports a nonfatal
`cactus_emmc_probe=1` while booting the existing `rd=md0` root, and
`rd=emmcroot0` once a dedicated HFS+ `iosroot` partition has been staged.
Multi-block reads use bounded CMD23/CMD18 PIO transfers (new in XNU, not yet
hardware-verified). No eMMC sector-write API is provided. The patch and its
SHA256 manifest entry apply cleanly to the local already-patched XNU source;
it has **not been compiled into a new XNU kernel or flashed**.

Next: build the 0121 XNU patch using the macOS kernel toolchain, validate
native runtime with the optional read-only probe, and stage a complete
Apple iOS HFS+ root with the dyld cache on accessible eMMC. The earlier
APFS-FUSE extraction returned I/O errors; reliable donor extraction and a
staging method that preserves the current Android system/userdata are
still required. The current eMMC reads do not prove Apple's dyld services,
SpringBoard or graphics pipeline work.

**Result:** Stage88 boot-image read access is hardware-proven. Native XNU
BSD block-driver support is implemented as an unbuilt patch. The user has not
approved overwriting any existing partition; Stage85/Stage87 rollback images
remain preserved.
