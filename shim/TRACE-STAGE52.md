# Stage 52: persistent XNU framebuffer debug and live Cactarwin banner

**Status (2026-10-24): XNU kernel rebuilt, shim boot image verified,
flashed to the Redmi 6A, and USB prehandoff PASSED.** The phone's
post-handoff screen output has not yet been observed for this version.
This stage does **not** establish a fully booted XNU system.

## Why Stage 51 appeared frozen

In `osfmk/arm/arm_init.c`, the existing XNU instrumentation called
`sweet_early_mark(20, "kprintf startup complete")` then immediately
`sweet_early_disable()` when `serial_init()` detected a serial backend.
In addition, `sweet_early_mark()` rejected stage numbers above 20.
The device owner **physically saw** the Stage51 kprintf startup line,
establishing native XNU early framebuffer writes. No later screen
output was available to locate subsequent initialization progress.

## Stage52 XNU changes

Patch `xnu/patches/0089-cactus-native-console-debug.patch` is applied
after `0088` and only changes `osfmk/arm64/sweet_early.c` and
`osfmk/arm/arm_init.c`:

- Retains the early framebuffer panic/progress writer on Cactus after
  `kprintf` startup and accepts progress stages 21–99.
- Draws a Cactarwin / Cactus-XNU banner after `serial_init()` at
  stage 20, when the framebuffer's serial backend has had the chance to
  initialize. Its labels make no unsupported CPU/GIC/timer claims and
  do not claim a missing payload when the Mach-O is present.
- Requests native `SERIALMODE_OUTPUT` if `serial_exists` is true,
  which is the existing XNU framebuffer serial driver registered by
  `fbcon_probe()`.
- Adds marks 21–37 around serial console, CPU idle, late platform
  setup, MMIO CPU mapping, timer initialization, chosen DRAM parsing,
  and `machine_startup()`. Each before/after pair helps isolate
  where initialization stops. Early panic output remains available.

Build: `austndoesui/Cactarwin` branch `stage52-cactus-debug`,
commit `6cdd82c`, GitHub Actions `40104893589` **SUCCESS**.

Downloaded Mach-O:
`../stage52-kernel-run40104893589/kernel.development.cactus`
(17,158,000 bytes, SHA256
`945e61817c333218a63c80ca0bd5b237bb95ee4c6724d429ae470c8e9e8a9d36`).

Payload: `shim/out/cactus/payload-stage52.bin` SHA256
`db7078d23a6ea5c0cf71cbd95ac5f5a814b705a74c293fc85e72f59630af565c`.
Relocated payload SHA256
`4fff93ad4d6a8b24da6d7ff3538d6497a490afc1ee2353b3bbe33f087b28864a`.

The new Mach-O entry is `0xfffffff007430488`, physical
`0x81430488`. The early bootstrap and vector moved `+0x3000`;
boot_args now lives at `0x824c0000`. Stage52 has a **separate pinned
static guard** `check_stage52_xnu.py` and revised runtime opcode
profiles; all 65 audited runtime opcodes match the shipped payload.
Older stage checks remain intact. The existing Stage49 physical scanout
guard and Stage50 video redirect remain in the shim.

## Hardware trial: 2026-10-24, ~20:54 local

With `fastboot devices -l` reporting serial `<REDACTED_DEVICE_SERIAL>`,
the existing guarded runner verified the image SHA256 and `product:
cactus`, flashed the boot partition successfully, and rebooted.

Image:
`shim/out/cactus/cactus-trace-stage-52-boot.img`, **45,524,992
bytes**, Android boot header v2, SHA256
`1db5be4481dc79c92b3dc68a26929d2b57a0d3dece606379689a3741c576869a`.
Manifest `.img.sha256` matches. **41 shim regression tests passed**
under Ubuntu; all Stage52 static and native runtime pins passed.

COM25 raw trace:
`../usb-captures/stage-cactus-20261024-205454-598/session-001-205504-948.bin`.
Decoder:
`python shim/decode-cactus-usb.py "CAPTURE.bin" --require-stage52 --show 100`.
**STAGE52 PREFLIGHT PASS: 79 valid frames, zero bad, gaps, duplicates,
or sequence regressions**. Verified:

- XNU real entry `0x81430488`, boot_args `0x824c0000`.
- framebuffer physical LK layer1 `0x7f4db000`; Stage49 scanout
  test pixels wrote and read back.
- Stage50 video redirect from `0x5e605000` to `0x7f4db000`.
- `0x5100` ADT handoff and `0x5200` Stage52 kernel identity markers.
- final `0x3900` watchdog-disarm prehandoff; no native XNU COM25
  progress expected after EL1 transfer.

The PowerShell runner timed out waiting for its watcher process, but
the watcher log confirms a complete `CLOSE ... bytes=4424 reason=capture
ended` and the saved trace decoder passes. This runner-timeout report
does not indicate a flashing or prehandoff failure.

**Next hardware evidence required:** What text appears on the device
after Stage52? In particular, whether the Cactarwin banner and marks
21–37 appear, and the **last displayed line** or native panic text.
The next source fix should follow this observed stopping point, not
speculatively short-circuit initialization.
