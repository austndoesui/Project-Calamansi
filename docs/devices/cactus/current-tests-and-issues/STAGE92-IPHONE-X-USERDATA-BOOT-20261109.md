# Stage92 — genuine iPhone X 20H392 filesystem on cactus (2026-11-09)

## Source and integrity

- Source: local iPhone X iOS 16.7.16 / build `20H392` IPSW, with OS,
  SystemOS, AppOS and kernelcache extracted in Ubuntu WSL.
- Full 16 GiB HFS root:
  `/home/lapdq/calamansi-iphone-x-20H392/calamansi-iphone-x-root-20H392.hfs`.
- Sparse userdata image:
  `/home/lapdq/calamansi-iphone-x-20H392/ios16-iphone-x-20H392-userdata.simg`,
  12,140,319,836 bytes; 27,869 sparse chunks; 16 GiB decoded logical size.
- The existing `tools/verify_ios_userdata_sparse.py` compared the entire
  decoded stream against the raw 16 GiB HFS root **byte-for-byte: PASS**.
  `userdata` is 18,136,153,600 bytes on the tested device.
- HFS contents were checked offline for genuine Apple `launchd`,
  `backboardd`, `mobileactivationd`, `SpringBoard` and the ARM64 dyld cache.

## Device flash

- `fastboot` serial `3184a8a17d2b`, `product: cactus`; `boot` capacity
  64 MiB. Owner explicitly authorized fastboot testing in this project.
- Host Windows `fastboot -S 64M flash userdata` used the sparse image via
  the WSL UNC path. Chunks **1–184/185 succeeded**, final chunk failed:
  `FAILED (remote: 'sparse image write failure')`. Do not call the initial
  complete sparse flash successful.
- Modified the existing `tools/repair_ios_userdata_sparse_tail.py` to
  accept the larger iPhone X HFS occupied range and validate that the final
  raw chunk contains the 4 KiB backup volume header. The repair retained
  the last 256 MiB of main allocated HFS data plus final backup header;
  intervening blocks encoded as DONT_CARE to preserve earlier writes.
- Repair file:
  `/home/lapdq/calamansi-iphone-x-20H392/ios16-iphone-x-20H392-userdata-tail.simg`,
  268,786,384 bytes, 489 sparse chunks, logical span 16 GiB.
- `fastboot -S 64M flash userdata <tail.simg>` succeeded on **all five**
  transport/write chunks. There has been no physical-device eMMC readback
  verifying the whole 16 GiB partition.

## Boot image and captured result

- Reused the existing Stage91 **root-block-open diagnostic kernel**; no new
  XNU kernel compile was required to test the new iPhone X filesystem.
- Boot image: `shim/out/cactus/cactus-trace-stage-91-boot.img`,
  SHA256 `8f432c70dab0ab9b478e95ca89a36476277b5fe97a689f8d0cf5ecb5bbf87a90`.
- `fastboot flash boot` and `fastboot reboot` both returned OKAY.
- COM25 capture:
  `_build/stage92-iphone-x-captures/stage-cactus-20261109-111302-737/session-001-111335-556.bin`.
  Decoding: **5,096 bytes, 91 valid frames**, no bad frames, gaps,
  duplicates or regressions; stage ID remains 91 because the shim/boot
  payload is Stage91.
- Shim markers: `0x4802` patched word `0x913e0d29` at `0x81ac042c`,
  `0x2303` XNU entry/boot arguments, `0x2800` Stage91 kernel SHA prefix,
  `0x3500` XNU handoff, and `0x3900` watchdog configuration.
- These frames describe **pre-XNU-handoff** activity. The Stage91 code
  changes aimed at `bdevvp` root-open are present, but this USB capture
  cannot establish whether root-open succeeded. Native framebuffer evidence
  is still required for HFS mount, actual Apple `launchd`/dyld execution,
  or the first SpringBoard frame. No real iOS GUI boot is claimed.

## Next blocking evidence

Inspect the current **physical framebuffer** after the Stage91 handoff,
especially a `bdevvp failed: open error=... rootdev=...` panic, any HFS mount
marker, or PID1/launchd crash. Use that result to focus native XNU changes;
another full IPSW extraction or userdata rewrite is not currently indicated.
