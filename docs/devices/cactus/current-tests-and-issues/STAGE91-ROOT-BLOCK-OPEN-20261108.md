# Stage91 — native iOS16 root block-open trace (2026-11-08)

Stage90 reached `ST68 mount root enter` and then XNU panicked at
`bdevvp failed: open`. In XNU's `bsd/vfs/vfs_subr.c` this path opens
the root block vnode with `FREAD`; `rootrw=1` does not itself make this
specific open writable.

## Focused kernel change

- Cactus MSDC `cactus_open` logs block major/minor, open flags, readiness,
  writable setting, GPT root extent, and its error code.
- The driver supports `DKIOCSETBLOCKSIZE` for its 512-byte sector size.
- `bdevvp` panic includes the actual error number and root block
  major/minor, to distinguish driver refusal from spec vnode errors.
- Patch manifest verified: 125 files, 122 patches.
- GitHub Actions kernel build: run `42479641169`, commit `2a56017`,
  branch `ci/cactus-ios16-root-open-20261108`, successful.
- Kernel SHA256:
  `b22e157d0eedc2344cd3ddf1d98afb5c23df46855f215eada70536334387a4ba`.

## Stage91 boot

- Boot image: `shim/out/cactus/cactus-trace-stage-91-boot.img`,
  62,283,776 bytes, SHA256
  `8f432c70dab0ab9b478e95ca89a36476277b5fe97a689f8d0cf5ecb5bbf87a90`.
- Offline verified native entry `0xfffffff00742c488`, boot args
  `0x834c0000`, all 41 pinned XNU instructions, GIC/FB mapping, 16MiB
  fallback HFS checksum, and `rd=emmcroot0 cactusroot=userdata
  cactusrw=1 rootrw=1`.
- Fastboot `3184a8a17d2b` reported `product: cactus` and a 64MiB boot
  partition. Only `boot` was flashed; sending/writing/reboot all OKAY.
  The 16GiB iOS HFS volume already on `userdata` was not reflashed.
- COM25 watcher was running before flash, 60-second capture:
  `_build/stage91-root-open-captures/stage-cactus-20261108-180616-855/session-001-180643-490.bin`.
  Decoded 5,096 bytes, 91 valid frames, zero bad, gaps, duplicates, or
  sequence regressions. Stage91 event `0x4802` checked word
  `0x81ac042c=0x913e0d29`, `0x2303` XNU entry/bootargs,
  `0x2800` kernel SHA prefix `b22e157d0eedc234`, `0x3500`
  native XNU handoff, `0x3900` watchdog config.

## Device result still needed

COM25 trace captures the shim before native XNU handoff, not the kernel's
root-device open result. Obtain the updated physical framebuffer panic,
especially `bdevvp failed: open error=... rootdev=...:...`, or evidence
of HFS mount, native Apple launchd, dyld, and SpringBoard.

The existing iOS HFS userdata image is retained, and no additional
userdata flashing is required for this root-open diagnostic.
