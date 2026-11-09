# Stage 83 — PID1 Mach-O postparse and executable paging

Stage82's native framebuffer completed the Mach-O command read and reported
`parse MachO=0`. The displayed three `segment64=8` values are ambiguous:
XNU's loader would normally abort that parse if a segment failed, so the
successful parse and those values must be interpreted together.

Stage83 retains the Cactus 4 KiB userspace mapping and standard Mach-O
loading behavior. The new XNU patch `0118-cactus-pid1-postparse-pagein.patch`
records the segment **name, parse pass and return code** and tracks PID1
through pagezero validation/commit, task halt and completion, map assignment,
and successful `load_machfile` return. It also observes actual `mockfs`
executable pager calls and their success/error status, without changing the
pager's I/O behavior. The existing verified `getpid(1)` syscall checkpoint
continues to be the only indicator that PID1 actually reached userspace.

## Build and device test, November 7 2026

- XNU source patch pushed in commit `dfe3729`; Actions run `42397764859`
  **SUCCESS** in 4m49s.
- Compiled kernel SHA256:
  `f3cf4c7978388b301703b02ea517e162e9e4c7f50e93cfcb26d645859fd9310c`
  (17,155,408 bytes).
- Relocated Stage83 XNU payload SHA256:
  `93297179dbfd26c73793c1a8d8a9bffd8103b7463b054605e07fa7ac163d7de2`.
  Exact native entry and **41 pinned instruction/layout checks passed**.
  Native entry `0x8142c488`, C entry `0x81abf9dc`, RAMDisk `0x824b8000`,
  boot arguments `0x824c4000`.
- Android boot-v2 image: `shim/out/cactus/cactus-trace-stage-83-boot.img`,
  size 45,522,944 bytes, SHA256:
  `95ef00615bed6150f01aa9a447d6346f0a31e0ca72d1f391177cae06fc6bba93`.
- Hardware: fastboot serial `3184a8a17d2b`, product `cactus` checked
  explicitly before flash. Boot partition write and reboot returned OKAY.
- COM25 capture:
  `usb-captures/stage-cactus-20261107-232509-682/session-001-232520-126.bin`.
  **80 valid frames**, zero corrupted, 10 missing sequence numbers. Kernel
  identity event `0x2800` matched `0xf3cf4c7978388b30` and XNU handoff
  event `0x3500` recorded native entry `0x8142c488` and boot arguments
  `0x824c4000`. Decoder correctly marks the capture incomplete due to
  missing sequence numbers.
- This COM25 implementation ends at native XNU handoff. PID1 progress after
  the handoff is visible only on the local framebuffer. The first postparse,
  pager, or user syscall result has not yet been observed in this test.

## Next device evidence

Read the newest `LAST` and `ERROR` markers on the native framebuffer.
Especially relevant are `PID1 pagezero begin/pass/commit`,
`PID1 task halt start/result/complete`, `PID1 map assigned`,
`PID1 load_machfile done`, and `ST83 PID1 executable pagein`. The
green `PID1 RUNNING` bar is reserved for an actual PID1 `getpid()`
syscall and is not assumed from any kernel-only progress marker.
