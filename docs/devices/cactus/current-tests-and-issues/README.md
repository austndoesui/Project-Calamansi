# Cactus — Current Tests & Issues

This directory holds the stage-by-stage **Redmi 6A (`cactus`)** native XNU
bring-up reports, iOS filesystem integration experiments, and their evidence.
The numbered records are historical snapshots; the latest test does not
automatically establish every earlier milestone on its own.

## Current checkpoint — 9 November 2026

| Area | Last supported result | Remaining issue |
| --- | --- | --- |
| Native XNU and minimal userspace | [Stage85](STAGE85-PID1-STACK-EXEC-FAULT.md): native PID 1 reached a real EL0 `getpid()` syscall; on-device framebuffer indicator observed. | This tested a minimal custom init, not Apple's full userspace. |
| Real Apple files | [iOS runtime HFS staging](IOS16-RUNTIME-HFS-STAGING-20261108.md) and [Stage92](STAGE92-IPHONE-X-USERDATA-BOOT-20261109.md): iPhone X 20H392 OS, cryptexes, dyld and SpringBoard extracted and packaged. | Apple service execution and graphical runtime unverified. |
| eMMC / root block open | [Stage92 framebuffer follow-up](STAGE93-IOS16-GUI-INTEGRATION-20261109.md): device `2:1` opened with error 0 and HFS `LOSRoot` mounted on `b(2,1)`; XNU reached `exec launchd`. | Apple launchd main, dyld startup, service spawning and GUI are unverified. |
| iPhone X userdata deployment | [Stage92](STAGE92-IPHONE-X-USERDATA-BOOT-20261109.md): 16 GiB root and sparse image byte-for-byte verified; main flash reached 184/185 chunks and five-chunk tail repair succeeded. | No full physical eMMC readback. |
| USB trace | [Stage92](STAGE92-IPHONE-X-USERDATA-BOOT-20261109.md): 91 valid prehandoff frames with zero decoding errors, including native XNU handoff marker. | Prehandoff trace does not show kernel root mount or `launchd`. |

**Stage93:** [Attempted integrated iOS16 GUI bring-up](STAGE93-IOS16-GUI-INTEGRATION-20261109.md).
Its CI build silently skipped the integration patch; the device booted an
unmodified kernel and showed the previous native framebuffer status.
**Stage94:** [Combined iOS16 service and dyld mapping fixes](STAGE94-IOS16-DYLD-SHARED-REGION-20261109.md)
corrects the skipped patch, starts native service sampling, and retries the
failed dyld shared-region mapping on cactus. CI explicitly verifies that
the kernel includes all of these changes. Its first hardware test hit the
stale Stage91 shim guard, causing a recovery reboot before native handoff.
**Stage95:** [Corrected shim instruction guards](STAGE95-SHIM-GUARD-CORRECTION-20261109.md)
verified the exact CI Mach-O, relocated payload, and C source guard values
before build; a hardware flash returned **91 valid COM25 frames and verified
native XNU handoff**. Its framebuffer confirms native HFS mount and the GUI
HID/sampler, but dyld shared-region mapping still returned error `0x4`.
**Stage96:** [4 KiB dyld shared-region fix](STAGE96-IOS16-DYLD-4K-SHARED-REGION-20261109.md)
built and flashed successfully. Native XNU handoff markers appeared in a
partially lossy COM25 capture. Apple launchd main and SpringBoard GUI remain
**unverified**.

## Reports and traces

- [Stage63–Stage96 test records](.) — numbered device bring-up,
  kernel/boot diagnostics, and filesystem experiments.
- [Older shim stage traces](shim-traces/) — historical `TRACE-STAGE*`
  records moved out of the shim source directory.
- [General cactus notes](../NOTES.md), [Benesse adaptation plan](../BENESSE-CACTUS-PORT-PLAN.md),
  and [USB diagnostic plan](../XNU-USB-LOGGING-PLAN.md) remain at device scope.

Runtime dumps, fastboot captures, generated root images, and IPSWs remain
local test artifacts and are intentionally excluded from the Git repository.
