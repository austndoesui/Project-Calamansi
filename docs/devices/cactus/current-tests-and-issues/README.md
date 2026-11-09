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
| eMMC / root block open | [Stage91](STAGE91-ROOT-BLOCK-OPEN-20261108.md): root-open patch built; diagnostic boot flashed. | Post-handoff framebuffer result of `bdevvp` open/mount not yet confirmed. |
| iPhone X userdata deployment | [Stage92](STAGE92-IPHONE-X-USERDATA-BOOT-20261109.md): 16 GiB root and sparse image byte-for-byte verified; main flash reached 184/185 chunks and five-chunk tail repair succeeded. | No full physical eMMC readback. |
| USB trace | [Stage92](STAGE92-IPHONE-X-USERDATA-BOOT-20261109.md): 91 valid prehandoff frames with zero decoding errors, including native XNU handoff marker. | Prehandoff trace does not show kernel root mount or `launchd`. |

**Next diagnostic:** inspect the device's native framebuffer immediately after
the Stage91 kernel handoff for `bdevvp` error code/rootdev, HFS mount
progress, or a real Apple `launchd` failure. A successful boot into iOS or
SpringBoard has **not** been demonstrated.

## Reports and traces

- [Stage63–Stage92 test records](.) — numbered device bring-up,
  kernel/boot diagnostics, and filesystem experiments.
- [Older shim stage traces](shim-traces/) — historical `TRACE-STAGE*`
  records moved out of the shim source directory.
- [General cactus notes](../NOTES.md), [Benesse adaptation plan](../BENESSE-CACTUS-PORT-PLAN.md),
  and [USB diagnostic plan](../XNU-USB-LOGGING-PLAN.md) remain at device scope.

Runtime dumps, fastboot captures, generated root images, and IPSWs remain
local test artifacts and are intentionally excluded from the Git repository.
