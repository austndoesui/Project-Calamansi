# Cactarwin Stage79 � virtual RAMDisk PID1 file-read repair (2026-11-07)

## Intent and source audit
Stage78 physically showed `ST78 mockfs cluster returned`, but the upper `vn_rdwr()` Mach-O header-read completion was not confirmed. Inspection of Stage77/78 XNU source proved that the cactus IOKit virtual RAMDisk has its own device I/O path: patch 0024 sets `mockfs_memory_backed = mi_mdev && mi_phys`; a virtual RAMDisk with `mi_phys=0` is handled through the backing device. Thus `mockfs_pagein()`'s physical-memory panic was not proven to be the live blocker. The earlier claim that this panic caused the hang was too strong.

## Changes
- Source repository: `F:\ROM\patching\redmi 6a xnu\stage54-xnu-build`; branch `stage61-cactus-gicr-id-guard`, commit `ccc8974` pushed to `austndoesui/Cactarwin`.
- Patch `xnu/patches/0114-cactus-mockfs-vnode-read-stage79.patch`: cactus virtual RAMDisk VREG reads use bounded `buf_meta_bread()` (same device path proven by mockfs mountroot's Mach-O signature check) and `uiomove()`, with offset, residual and partial EOF handling. This avoids the Stage78 `cluster_read()` read path during normal `VNOP_READ`.
- The existing virtual-device `cluster_pagein()` and `mockfs_strategy()` are kept for demand paging because they correctly route to IOKit device I/O; physical-memory UBC mapping is preserved. The unexpected physical-memory page-in now reports `ENOTSUP` instead of panicking, while `mockfs_blockmap()` avoids panic at partial EOF.
- GitHub workflow required-patch audit includes Stage78 and Stage79.
- Minimal new framebuffer markers: `ST79 mockfs devread enter/finished/ERROR`. Existing `ST78 hdr err=...` and `ST78 MachO activator enter` indicate further PID1 progress.

## Build and provenance
- GitHub Actions run `42287548183` **SUCCESS**, 7m35s: https://github.com/austndoesui/Cactarwin/actions/runs/42287548183.
- Kernel: `../stage79-kernel-run42287548183/kernel.development.cactus`, 17,122,288 bytes, SHA256 `a0d33e9f8c73e9b4686efbffe3742f2a381375ddf45c164300f4069d430de362` matching `SHA256SUMS`.
- `tools/stage79_pack_kernel.py` verifies compiled provenance markers and the Actions checksum, packages signed minimal PID1 from Stage78 without overwriting Stage78.
- Relocated XNU payload SHA256 `2c6cbde529f40f2d6a9e43b898cd6060b1033a5b3c8ca8a954179501ee5fcd4c`.
- Native entry PA remains `0x8142c488`; C prologue moved from Stage78 `0x81abe43c` to `0x81abe57c` (+0x140), and checkpoint from `0x81abea6c` to `0x81abebac`. `shim/check_stage79_xnu.py` verifies 41 AArch64 opcode pins plus memory layout, GIC, ADT, signed RAMDisk, boot_args, page tables and image hash.
- Stage79 Android v2 boot image `shim/out/cactus/cactus-trace-stage-79-boot.img`, 45,506,560 bytes, SHA256 `9cb0e676790d7d48a0298f36fccab445e24b3d599f0a39b617869054daae7819`. Strict guard, header validation, build, and hash passed. Stage78 image remains intact: SHA256 `79c387f5c04ebdcdf9c3bf4e9bdbfc83553a489fab56e6f88da1b29b70e8b931`.

## First hardware run
Device serial `<REDACTED_DEVICE_SERIAL>` confirmed in fastboot. Flashed Stage79 using `shim/run-stage49.ps1 -Stage 79 -CaptureSeconds 60`; fastboot send, write, and reboot each returned **OKAY**. COM25 capture `../usb-captures/stage-cactus-20261107-020337-921/session-001-020348-093.bin`: 4,480 bytes, 80 valid frames, zero corrupt/noise, 10 missing sequence numbers. Stage79 XNU identity event `0x2800` (hash prefix `a0d33e9f8c73e9b4`) and native handoff `0x3500` (entry `0x8142c488`, boot_args `0x824c0000`) recorded. As with Stage78, USB logger ends at the transition: **new PID1 reading, Mach-O completion and userspace execution are not yet established by this trace**. The physical framebuffer's last Stage79 message is the next critical evidence.
