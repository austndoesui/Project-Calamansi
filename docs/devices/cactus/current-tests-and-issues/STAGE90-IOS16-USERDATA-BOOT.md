# Stage90 — native iOS 16 root on cactus userdata (2026-11-08)

The Redmi 6A `cactus` now has a 16 GiB HFS+ iOS 16.7.16 filesystem
prepared in `userdata`, with the Stage90 native XNU shim flashed to `boot`.
**Apple launchd, dyld, SpringBoard, and an iOS GUI remain unverified.**

## Provenance

- Source kernel: GitHub Actions run `42474795094`, successful, branch
  `ci/cactus-ios16-userdata-20261108`, revision `8d624466`.
- `kernel.development.cactus` SHA256:
  `376706e72c2f15eb81e4aeaa9222f9772aacadeb021e2d25e018959ee3ec664e`.
- Stage90 Android boot image:
  `shim/out/cactus/cactus-trace-stage-90-boot.img`,
  size 62,283,776 bytes, SHA256
  `46b680097efa6aa9ca9608005790b13aa7044f2f535d339de5052475e669fcaa`.
- Root selector: `rd=emmcroot0 cactusroot=userdata cactusrw=1 rootrw=1`.
  The 16 MiB known-good HFS+ image remains in the boot payload as an
  audited fallback segment, but is **not** selected as the root volume.
- Stage90 preflight passed **41** pinned XNU instruction checks,
  framebuffer/GIC, relocation, and native boot arguments. All patched
  XNU files passed the 124-file/121-patch manifest verification.

## Userdata filesystem flash

- Raw HFS+ volume: 16 GiB at
  `/home/lapdq/calamansi-ios16-sweet-v1.hfs`.
- Android sparse image:
  `_build/ios16-runtime/ios16-userdata.simg`,
  6,263,998,900 bytes. All 12,738 chunks were decoded and compared
  bit-for-bit against the source raw HFS+ image offline.
- Fastboot device serial `3184a8a17d2b` / product `cactus`;
  `userdata` partition size `0x438ffbe00` (greater than 16 GiB).
- Initial full sparse flash: chunks 1–94/95 `OKAY`;
  final chunk reported `FAILED (remote: 'sparse image write failure')`.
- Recovery: generated
  `_build/ios16-runtime/ios16-userdata-tail.simg`, a 268,905,168-byte
  Android sparse **repair**, preserving the last 256 MiB of source
  filesystem data, its zero-filled gaps and final 4 KiB backup HFS+
  header. Previous blocks and unallocated trailing free space are
  represented as DONT_CARE (left untouched). All selected RAW/FILL
  payload bytes were compared against the original sparse source.
  All **five of five** fastboot repair chunks completed successfully.
  This is a sparse repair after a partial flash; it is not an
  independent readback of the entire eMMC partition.

## First device boot

Stage90 boot flash returned `OKAY` for sending and writing, then fastboot
reboot returned `OKAY`. The COM25 watcher was running beforehand:
`_build/stage90-userdata-captures/stage-cactus-20261108-172734-177/`.

Captured `session-001-172815-374.bin` shows:

- `0x4802`: audited Stage90 target word
  `0x81ac042c = 0x9107dc00`.
- `0x2303`: XNU entry PA `0x8142c488`, boot args PA `0x834c0000`.
- `0x2800`: CI SHA prefix `0x376706e72c2f15eb`.
- `0x3500`: native XNU handoff.
- `0x3900`: watchdog mode `0x5c`.

USB logging is provided by the shim before handoff, so these markers
do not verify that XNU mounted HFS+, launched Apple launchd, or reached
SpringBoard. Native framebuffer evidence is needed to establish the
next actual failure or success. Preserve the Stage89 boot image as
rollback. No Android `system`, `vendor`, or bootloader partitions
were flashed in Stage90.
