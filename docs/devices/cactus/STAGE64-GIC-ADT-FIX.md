# Stage64 — correct actual Cactus GIC physical mapping

## Root cause

Stage63's embedded Apple Device Tree, inspected from the **relocated payload
bytes**, incorrectly contained QEMU GIC physical regions: `/arm-io/ranges`
base `0x01000000`, and `/arm-io/gic/reg` relative pairs
`(0x07000000,0x10000)` and `(0x070a0000,0x100000)`. These map physical
`0x08000000` (GICD) and `0x080a0000` (GICR). Stage62/63 physical EL2
register scans independently established real Cactus GICD `0x0c000000`,
size `0x40000`, and GICR `0x0c100000`, size `0x200000`, with eight valid
redistributor frames (PIDR2 `0x3b`). The mismatch explains XNU's
`find_gicr_pe_base()` panic without needing a speculative kernel MMIO shim.

## Fix

`tools/stage27_pack_kernel.py --stage64-cactus-gic` now replaces only the
32-byte GIC `reg` property with the audited relative pairs
`(0x0b000000,0x40000)` and `(0x0b100000,0x200000)`. It verifies the
old QEMU values and SoC ranges before changing anything, and preserves the
exact ADT size, Stage63 XNU Mach-O, live LK framebuffer, bootargs and
signed diagnostic RAMDisk. `shim/check_stage64_xnu.py` pins the entire
relocated payload SHA256 and verifies those MMIO addresses as well as the
existing native XNU startup/ramdisk invariants.

Stage64 relocated payload SHA256:
`51d6cd4877bce3036c411ff4b6adc37afaf21ea34699b9554ea270c053714072`.

Stage64 Android boot-v2 image:
`shim/out/cactus/cactus-trace-stage-64-boot.img`, 45,541,376 bytes,
SHA256 `284c88173ed18660027d0eb7ce0e3fb746d5a9475b0b0ce2719435252218ebae`.
The build and strict payload guard passed; all 16 USB decoder tests passed.

## Hardware test — 2026-11-03

Fastboot detected serial `<REDACTED_DEVICE_SERIAL>`. Stage64 boot partition flash and
reboot both returned `OKAY`. The USB watcher captured 4,480 bytes, **80
valid CLOG frames, zero corrupt and zero noise**, with **11 missing frames**
(sequence numbers 64–74). Stored at
`F:\ROM\patching\redmi 6a xnu\usb-captures\stage-cactus-20261103-105852-964\session-001-105902-673.bin`.

Stage64 trace includes GICD PIDR2 `0x3b`, eight GICR PIDR2 `0x3b`
frames from `0x0c100000` through `0x0c1e0000`, handoff event `0x2303`
to native entry `0x8142d488`, XNU identity event `0x2800`, and handoff
event `0x3500`. Because 11 required prehandoff records are missing, the
strict trace validator returns INCOMPLETE. After handoff the raw USB logger
does not prove how far native XNU runs. **The Stage63 GICR panic has not
yet been confirmed resolved on the display.** Do not claim iOS userland
or PID1 booted without visible framebuffer/native logs.

The automated flash wrapper prematurely reported `No COM25 frames captured`
even though its watcher later saved valid frames; it now retries and searches
only the current run's capture directories.
