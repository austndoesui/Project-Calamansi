# Stage65 — native XNU to diagnostic PID1, with persistent status bar

## Purpose and verification boundary

Stage64 solved the GICR ADT address mismatch. The live framebuffer then
confirmed XNU VM/IOKit startup and CPU0 SGI delivery. Its last known
line was `ktrlage_register_subsystem_strings: set subsystem 8 strings`;
BSD root mounting and PID1 execution remain unknown.

Stage65 preserves the Stage64 GICD/GICR physical regions
`0x0c000000` and `0x0c100000`, native XNU startup, console framebuffer,
`rd=md0` RAMDisk and USB prehandoff diagnostics. The sole new boot goal
is to prove execution of the source-built diagnostic userspace process.

## Bottom-of-screen status

`xnu/patches/0100-cactus-pid1-status-stage65.patch` was applied on top of
the earlier native console patch. It reserves the final 16-pixel row of the
720x1440 framebuffer, independent of the seven-row header and circular
kernel log area. **Amber** (`0xffb36a15`) displays
`PID1 WAITING - BSD/root/exec pending` during kernel initialization.
**Green** (`0xff168c43`) displays
`PID1 RUNNING - user syscall verified` only if the real BSD `getpid`
syscall runs for process ID 1. Allocating an `initproc` kernel object alone
cannot trigger green.

`tools/cactus-init-stage65.S` calls `getpid` immediately upon userspace
entry, before attempting to open `/dev/console`. If opening the console
fails, the process may still park, but the green bar will already prove
userspace syscall entry. The source-built signed ARM64 Mach-O root is
`shim/out/cactus/stage65-init/cactus-init.macho`, SHA256
`f0b8d9f4e5d841691efe23b1521e756b743665484be82b9e7082c71626e7fe5d`.

## Build and guards

GitHub Actions CACTUS DEVELOPMENT run **41586007450** succeeded on
commit `4b70566`, using the additive XNU patch 0100. Verified kernel:
`../stage65-kernel-run41586007450/xnu-kernel/kernel.development.cactus`,
17,158,448 bytes, SHA256
`8b9d47e456c92f59f04e546f7a047b6fb191f211fd079f274707b2bb72dfb1f5`.
`llvm-nm` confirmed `_fbcon_stage65_pid1_running` and `_getpid`; the
kernel includes both status-bar strings.

`tools/stage27_pack_kernel.py --stage61-live-fb --stage64-cactus-gic
--stage65-cactus-pid1` repacks Stage65 from this exact kernel and the
matching PID1. No earlier payload is overwritten. The relocated payload
`shim/out/cactus/linux-chainload/stage65-relocated-payload.bin` is
SHA256 `741af2fc4f5ae3302a76f10243e79ef91cb6e9cbf9916ec79cd7eeae764bb08b`.

`shim/check_stage65_xnu.py` pins its SHA, native startup and branch
instructions, early C address `0x81ac352c`, continuation `0x81ac3b5c`,
signed PID1, physical GIC regions, framebuffer, ADT RAMDisk and `rd=md0`.
The strict guard passed, as did all 16 decoder unit tests. The Android
boot-v2 image was generated at
`shim/out/cactus/cactus-trace-stage-65-boot.img`, 45,541,376 bytes,
SHA256 `ae0dc7bf8b061bc022de860d02dff997e667d8d54fca8606c96d7c90373c7837`.

## Hardware test on November 3, 2026

Verified fastboot serial `<REDACTED_DEVICE_SERIAL>`, product `cactus`, and the
built image SHA256. Both `fastboot flash boot` and `fastboot reboot`
succeeded. COM25 captured **77 valid frames**, no corrupted frames,
and **14 sequence gaps**, including native-entry and rebuilt-kernel
handoff markers 0x2303 / 0x2800 / 0x3500. All eight physically measured
GICR frames still reported PIDR2=0x3b. Saved capture:

`F:\ROM\patching\redmi 6a xnu\usb-captures\stage-cactus-20261103-113252-696\session-001-113302-972.bin`

Strict prehandoff validation is **INCOMPLETE** because records were dropped.
The PC-side USB shim does not transmit later native framebuffer logs.
**No green PID1 indication has been observed or reported yet.** The owner
must provide the current on-screen STATUS and bar color to distinguish
normal BSD/root/exec progress from a hang. The original Stage64 rollback
image remains available.

## After diagnostic PID1

Successful green status proves a source-built process got into XNU's
syscall interface. To boot *iOS* rather than only diagnostic XNU, a
working root filesystem, file I/O, matching dyld/shared cache,
Apple launchd and essential iOS services remain necessary. SpringBoard
also needs platform and graphics integration. Do not treat the stand-in
SWEET security, battery, touch or framebuffer services as original iOS
hardware drivers.
