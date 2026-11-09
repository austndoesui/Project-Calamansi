# Stage63: consolidated native XNU bring-up

Goal: make one source-built kernel and one guarded hardware trial cover the known GIC failure, CPU readiness, and subsequent BSD/PID1 progress. Avoid a new build for each log line.

## Verified baseline

Stage60 reached the SGI8 readiness check but reported `0x3ff00000040`; Stage61 added GICR PIDR2 validation and panicked earlier in `find_gicr_pe_base()`. Stage62 used the identical Stage61 XNU payload, successfully flashed, and captured 204 valid COM25 frames (12 sequence gaps). The complete physical GICR census survived: GICD PIDR2 `0x3b`, eight redistributors PIDR2 `0x3b`, CPU0 GICR PA `0x0c100000`, TYPER `0`, MPIDR `0x80000000`. This proves readable physical GICv3 frames before XNU, not native XNU mapping or interrupt delivery.

## Single-build implementation scope

1. Before `find_gicr_pe_base()` in native XNU, record the computed SoC base, ADT GIC offsets/sizes, resulting physical PA, mapped virtual GICD/GICR bases, and per-frame PIDR2/TYPER. Include the full 64-bit MPIDR and affinity. Report the values on the framebuffer before any panic; keep a compact persistent summary if startup stops.
2. Correct confirmed PA/VA/memory attribute or frame-selection defects in the same source build. Validate the expected CPU0 frame `0x0c100000` against Stage62 hardware values. Do not silently accept a zero-filled frame or fake CPU readiness. Avoid unconditional mapping bypasses or undocumented GIC security changes.
3. Run the complete existing Stage60+ native initialization path, including wake/readback of GICR_WAKER, Group1NS/PPI/SGI enable and pending registers, ICC_SRE/PMR/IGRPEN, exception routing, and actual interrupt receipt. Bound timeouts and preserve the complete failure reason.
4. Keep full native framebuffer logging enabled through CPU initialization, Mach startup, IOKit, BSD entry, root mount, and PID1 attempt. Reuse existing iOS16 diagnostic RAMDisk and 8x16 console. Print a final persistent milestone showing the farthest genuine checkpoint.
5. Rebuild XNU once, then regenerate branch/opcode/SHA pins and package one new Android boot-image-v2 through the existing guarded pipeline. Run full source/payload/ADT/RAMDisk guards, all WSL shim tests, and a single 120-second COM25 hardware capture when fastboot is available.

## Acceptance criteria

The image must retain the Stage62 physical census, prove native reads from a valid CPU0 redistributor, and advance beyond the Stage60 SGI checkpoint. If it fails, the same run must distinguish address mapping, redistributor wake/security, CPU interface, actual SGI delivery, or later Mach/BSD/PID1 startup. Do not claim iOS boot until an actual root mount and PID1 execution are observed. Keep earlier tested images for comparison.

## November 3 implementation checkpoint

An initial native Stage63 GIC mapping/identity instrumentation patch was
generated as `0099-cactus-gicr-map-census-stage63.patch` in the isolated
`../stage54-xnu-build` build worktree, commit `8e09cda` on
`stage61-cactus-gicr-id-guard`. The patch logs the computed SoC base,
ADT offsets, XNU mapped addresses, MPIDR and per-frame PIDR2/TYPER. It
does not yet correct MMIO mapping or prove SGI delivery.

GitHub CACTUS DEVELOPMENT build run `41507227468` completed **SUCCESS**.
Downloaded `../stage63-kernel-run41507227468/kernel.development.cactus`
(17,174,712 bytes; SHA256
`c9b059c9dad73f49999c073a701fdbc2328858bbd6ccf30b18b7634222cfb51d`).
The new 11-segment source payload is
`shim/out/cactus/payload-stage63.bin`; relocated payload is
`shim/out/cactus/linux-chainload/stage63-relocated-payload.bin`
(16,574,048 bytes, SHA256
`f7100f3d9f5f17fb4b1dcdad47b8ba13d06037901416566334e2362ef8c9c747`).

**Packaging is incomplete.** The Stage61 exact early-C prologue guard
rejected the newly compiled kernel (`Stage61 early C entry prologue changed`).
Its bootstrap/branch offsets and opcodes must be independently audited and
repinned before building an actual Stage63 boot image. The already downloaded
kernel is a source-built candidate, not a validated flashable Stage63 image.
No Stage63 flash or hardware test occurred.
