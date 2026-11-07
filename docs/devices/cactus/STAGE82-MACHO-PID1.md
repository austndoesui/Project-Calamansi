# Stage 82 — 4 KiB Mach-O user mapping and PID1 activation

User-observed Stage81 framebuffer milestones:
* `ST81 PID1 VNOP_READ returned`
* `ST81 PID1 vn_rdwr returning`

Those milestones prove that the first executable read exited the
filesystem and the `vn_rdwr_64` wrapper. They do not prove that the
caller received the header or that the first userspace instruction ran.

Stage82 patches `bsd/kern/kern_exec.c` and `bsd/kern/mach_loader.c`.
Cactus now chooses the 4 KiB userspace page shift for ARM64 Mach-O
loading, consistent with its 4 KiB translation granule. The ordinary
Mach-O loader remains active. Stage82 also exposes, on the native
framebuffer, the return from the exec header read, the activator
entry/result, UBC object status, Mach-O command read status and residual,
and Mach-O 32/64-bit segment mapping results. The minimal PID1 executable
remains the existing static ARM64 Mach-O.

## Build and hardware validation, November 7 2026

* XNU patch commit `ed7be7d`; CI run `42391112974` passed.
* Kernel `kernel.development.cactus`: SHA256
  `db8fa92517586342a1465b458058a052038708b6f75c9f53b34edc84ca2e68a6`,
  17,139,024 bytes.
* Stage82 relocated payload SHA256
  `5f9b2560587afd575ed801e6be24593b1d6c96e666b42c9007df752f2b0c2e6a`.
  Exact pinned XNU instructions and 4 KiB hardware/ADT/RAMDisk layout:
  **41 checks passed**. Native entry PA `0x8142c488`, C entry PA
  `0x81abf6dc`, RAMDisk PA `0x824b8000`, boot args PA `0x824c4000`.
* Boot image `shim/out/cactus/cactus-trace-stage-82-boot.img`:
  45,522,944 bytes; SHA256
  `3a619eb206f6625fb9721de615c0ecb463bb5b3e0385e7ec93d38442215035cc`.
  Android boot image v2 structure and image checksum verified.
* Fastboot product `cactus` verified, target serial matched, boot partition
  write and reboot both returned OKAY.
* Captured `usb-captures/stage-cactus-20261107-222622-808/session-001-222634-886.bin`:
  76 valid frames, 0 corrupt, 14 sequence gaps. Transport records keep
  the `stage=63` tag even when the kernel identifies Stage82 via event
  `0x2800`. That event carried exact kernel SHA prefix
  `0xdb8fa92517586342`. Event `0x3500` confirmed native XNU handoff,
  entry `0x8142c488`, boot args `0x824c4000`.
* The COM25 trace is **incomplete** due to the 14 gaps. The observed
  handoff is independently identifiable in the captured records.
  Native framebuffer Stage82 PID1 outcome has not yet been reported.
  No userspace execution is claimed.

## Next actionable evidence

Read the last `ST82` framebuffer event after native boot. If the
`ST82 PID1 exec read returned` event appears, compare the following
`ST78 hdr err/rem/magic` and `ST80 PID1 MachO header valid` results.
The Stage82 loader events should then locate either an activator error,
VM map mismatch, command read failure or segment mapping result.
After successful Mach-O loading, the next unsolved boundary is executable
page fault/paging and first user instruction; full iOS userspace also
requires dyld, launchd, and its runtime services.
