# Stage 84 — PID 1 first syscall without console dependency

Stage 83's native framebuffer reached `PID1 load_machfile done`, confirming
that the kernel successfully produced the initial executable VM map.
The minimal `tools/cactus-init.S` had a concrete observability bug:
it attempted `open("/dev/console")` before calling `getpid()`, and
branched to a permanent spin on open failure. This could prevent the green
`PID1 RUNNING` bar even if the program successfully entered EL0.

Stage 84 changes the first userspace syscall to `getpid()` immediately
after stack alignment. The existing `kern_prot.c` PID1 getpid hook sets
the green bar only for actual PID1 user syscall execution. Console open
and writes are now optional; a failing console open enters a loop which
continues issuing `getpid()` rather than blocking that proof.

The Stage 84 XNU patch additionally traces the remaining exec path:
Mach-O loader return to the caller, PID1 zone reboot checks, VM map swap,
thread-state activation, stack creation, Apple argument copying,
prefault, task switch and signature processing. Existing XNU validations
and code-signature logic are retained.

## Build and device evidence, November 7 2026

- XNU patch and minimal init source pushed as commit `4dcbe3b`.
- GitHub Actions macOS kernel build `42400116384` **SUCCESS**.
- Kernel `kernel.development.cactus` SHA256:
  `dae21a356c72c79f6308e6fad36eca3ad125c15a53644bca61fb8f9d55569ddb`,
  17,139,080 bytes.
- Rebuilt 16,635-byte signed PID1 ARM64 Mach-O SHA256:
  `0d96929c37ea20608758e871fb102bca5be44135b39e459fa55e3064509f29b1`.
  The old Stage83 signed binary is preserved under
  `_build/stage84-backups/stage83-cactus-init.macho`.
- Relocated payload SHA256:
  `0e388f6c0fac708ec6a514dd89cc94c03e057819bc041935903f4d6530ae934e`.
  All **41 strict XNU instruction/layout checks passed**, including signed
  init digest, entry `0x8142c488`, C entry `0x81abfbbc`, and boot args
  `0x824c4000`.
- Boot image `shim/out/cactus/cactus-trace-stage-84-boot.img`:
  Android boot image v2, 45,522,944 bytes, SHA256
  `058b98910c60226ba451fa93ad7461771197c7e5ac423bd0d42c485b427702d9`.
- Hardware: verified fastboot serial `3184a8a17d2b` and product `cactus`
  before flashing. Sending, writing the boot partition and rebooting
  returned OKAY.
- COM25 capture:
  `usb-captures/stage-cactus-20261107-235429-114/session-001-235438-354.bin`.
  **79 valid frames**, zero corrupt, 11 missing sequences. Stage84 kernel
  identity event `0x2800` included SHA prefix
  `0xdae21a356c72c79f`. Native XNU handoff event `0x3500` reported
  entry `0x8142c488` and boot args `0x824c4000`.
- This COM25 trace ends at native XNU handoff, and its sequence gaps cause
  the decoder to label the capture incomplete. We have **not yet observed**
  the framebuffer after handoff, so there is no evidence in this run that
  the green PID1 bar has turned on or that iOS userspace has started.

The next decisive physical observation is the green `PID1 RUNNING` bar,
or the newest Stage84 event in the fixed framebuffer history. If it
stalls, the Stage84 event identifies which remaining exec transition
completed or failed.
