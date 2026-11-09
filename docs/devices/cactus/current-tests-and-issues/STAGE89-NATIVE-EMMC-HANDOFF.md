# Stage 89 — native XNU read-only eMMC handoff (2026-11-08)

The macOS CI build from [run 42465942432](https://github.com/austndoesui/Project-Calamansi/actions/runs/42465942432)
produced a real arm64 XNU DEVELOPMENT cactus kernel, SHA256
`3fa61a4f8a246abb08e53a8770175959e21d284d7509b70098c3922503318a7a`.
It includes the read-only cactus MSDC/eMMC BSD driver from patch 0121.

Stage 89 repacks that kernel with the **existing Stage87 16 MiB HFS+ root**,
SHA256 `cf281dccb5b69add3ef01070a3ed21202287727dffa982772fd705ff4acaeea9`,
and boot args:

`debug=0xc rd=md0 unentitled_ios_sim_launch=1 sweetfb_noconsole=1 cactus_emmc_probe=1`

The kernel entry is `0xfffffff00742c488`, relocated at PA
`0x8142c488`. The new kernel footprint ends at VA
`0xfffffff0094bc000`, putting the shim's boot args at **PA
`0x834c0000`** and the 16 MiB root at `0x824bc000`.
`tools/stage89_pack_kernel.py` pins the CI artifact and root; the
`shim/check_stage89_xnu.py` check covers the exact root bytes, framebuffer,
GIC, command line, loader memory ranges and 41 instruction pins.

## First hardware test and correction

The first Stage89 boot image SHA256
`80fa78f1e40ab6efb80a7218fc9bfafbfa2d9c8a7dcba347495738921ac785b7`
was flashed successfully, but the shim stopped before native XNU handoff
with **status `0x510`**. The original Stage85/86 shim preflight expected
boot args `0x834bc000` and five older early-C instruction words. The
captured relocated Stage89 kernel differed at those exact values.
Original image is preserved at
`shim/out/cactus/cactus-trace-stage-89-pre-guard-fix-boot.img`.

The fix adds `CACTUS_STAGE89_NATIVE` to the Stage89 build only and
updates the preflight PA and the five exact new C-level instruction pins
without disabling the existing guards. It also updates the Stage48
read-only checkpoint and COM25 SHA identity. An additional offline audit
confirmed **47** pinned instruction, early-boot and exception-vector words
match the actual relocated Stage89 payload, with **zero mismatches**.
The 123-file/120-patch manifest check, Python syntax and shell build
validation passed.

## Corrected hardware test

Corrected image:
`shim/out/cactus/cactus-trace-stage-89-boot.img`, 62,283,776 bytes,
SHA256 **`f9968b4fb327b11bfd193a2f7e2f02ccc1e8d0b16b1a4517c9aa5dfbd65b6a88`**.
Fastboot confirmed `product: cactus` and serial `3184a8a17d2b`.
The watcher was running before the successful boot-partition flash/reboot.

USB capture:
`_build/stage89-guard-fix-captures/stage-cactus-20261108-150924-689/session-001-150935-264.bin`.
The decoder reports **91 valid frames**, zero bad frames, zero gaps.
Events show the eleven kernel/ramdisk segments loaded, stage20b guard
passed (`0x20a0`/`0x2204`), framebuffer and MMIO checks, then:

- `0x2303`: physical XNU entry `0x8142c488`, boot args `0x834c0000`.
- `0x2800`: pinned CI kernel ID `0x3fa61a4f8a246abb`.
- `0x3500`: native entry/bootargs handoff marker.
- `0x3900`: RGU watchdog disarmed with mode `0x5c`.

These events **confirm the corrected shim reached the native XNU
handoff boundary**. COM25 is a prehandoff logger and cannot prove the
native XNU eMMC probe completed or that launchd started. Native
framebuffer text or a separate post-handoff trace is still needed.
No Android system or userdata partitions were changed.
