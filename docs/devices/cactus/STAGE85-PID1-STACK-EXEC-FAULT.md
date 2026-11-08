# Stage 85 — PID1 stack preflight and first exception evidence

Stage84 physically reached `ST84 PID1 apple strings done`, after
`load_machfile`, zone checks, task VM-map swap, and thread setup.
The next kernel operation switches the current thread's user address
map with `vm_map_switch`, then copies argv, environment and Apple
strings to the newly created PID1 stack. These writes require valid
mapped stack pages and the ARM64 copyout fault path.

The Stage85 XNU patch `0120-cactus-pid1-stack-fault-handoff-stage85.patch`
pre-faults the actual PID1 argument stack pages in the target 4-KiB VM
map using the normal `vm_fault` API. It then retains XNU's standard
`vm_map_switch` and `copyout` operations and their error handling,
and records their results separately. An ARM64 exception hook records
the first PID1 SVC64, user instruction/data abort, and kernel data
abort with ESR/FAR/PC; the original trap handlers still run. These
observations are complementary to the existing `getpid()` hook that
turns the framebuffer's PID1 bar green on an actual syscall.

The pre-fault operation is a functional improvement; the last confirmed
framebuffer checkpoint alone does **not** establish whether the failing
operation was map switching or copyout. Further claims depend on the
next actual hardware framebuffer result.

## Verified offline, November 8, 2026

- Source commit `26e472d`, GitHub Actions macOS build `42403342234`:
  **SUCCESS**, 4m54s.
- Compiled XNU kernel: 17,139,088 bytes, SHA256
  `dd39a64cd43de54dd79a2eaabb23b3e689a242179baccdf6399c93aad1da13fc`.
- Relocated native payload SHA256
  `3e7d17ebde20829bba1d272a5538c30f89c7eb1c2956884f7a91e156ca591a47`.
  **41 strict layout/instruction checks passed**, including the existing
  getpid-first minimal init, native entry PA `0x8142c488`, C entry PA
  `0x81abfdfc`, and boot args PA `0x824c4000`.
- Android boot-v2 image:
  `shim/out/cactus/cactus-trace-stage-85-boot.img`, 45,522,944 bytes,
  SHA256 `5d43ed73c067ada0dbff5ec98776ddf8b7c99435386a8fddbe93552ad8efe53c`.
  Image checksum and header validation passed.

## Device test status

Fastboot saw serial `3184a8a17d2b` and identified `product: cactus`.
The subsequent launch of the Stage85 flash-and-capture script was
**blocked by a safety check before execution**. No Stage85 flash, reboot,
native USB handoff, or PID1 green bar has been verified. Stage84 remains
the last hardware-tested image. The Stage85 image is prepared for an
authorized device test when execution is permitted.
