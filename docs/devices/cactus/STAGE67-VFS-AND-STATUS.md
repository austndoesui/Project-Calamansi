# Stage67 — visible status indicator and BSD VFS checkpoint isolation

## Corrected diagnosis from Stage66 framebuffer

The latest reported framebuffer still ends at
`ktriage_register_subsystem_strings: set subsystem 8 strings` and retains
`STATUS ST56 CPU all initialized`; the PID1 bar was not visible. The exact
string comes from `bsd/kern/kdebug_triage.c` called by `decmpfs_init()`
in `bsd/vfs/vfs_init.c`. **BSD is already executing and has reached VFS
initialization**. This corrects earlier reports that BSD had not started.

The final printed line does not by itself prove that `decmpfs_init()` is
stuck. Its next operation sets `done=1`, then VFS calls
`nspace_resolver_init()`. The absence of later messages could also be due
to missing instrumentation or a blocked operation farther downstream.
There is still no evidence of root mounting or PID1's `getpid()` syscall.

## Stage67 fixes

Incremental XNU patch
`../stage54-xnu-build/xnu/patches/0102-cactus-visible-bar-vfs-stage67.patch`
was committed as `1e4f422` on the experimental Cactarwin branch. It:

- Moves the existing PID1 amber/green bar from row0 to **row5**
  (80–95 physical scanlines), replacing the dashed divider directly
  above the STATUS line. This is a visible header location, unlike the
  bottommost scanline and potentially clipped topmost row.
- Initializes the amber state when the framebuffer is first configured.
  Green remains contingent on a real `getpid()` syscall by process 1.
- Adds native framebuffer STATUS and kprintf markers immediately before
  and after `decmpfs_init()`, around `nspace_resolver_init()`, and after
  the return from `vfsinit()` inside `bsd_init()`.

These are diagnostic markers only. No BSD mount logic, syscall semantics,
or device driver paths were bypassed.

## Build and hardware state

GitHub CACTUS DEVELOPMENT Actions **41594140727** completed successfully.
The compiled XNU kernel SHA256 is
`7d389b5181d3515cc201f6719585799b30ddf37f5760215dd2974951daf35c6c`.
The relocated payload SHA256 is
`cac6aa852eec8c63357b967c1099229a15a411b61bf785bba8fe219cad9c4aae`.
Native entry address, join, post-handoff opcode and all 17 critical branch
pins match the audited Stage66 build. Corrected physical GICD/GICR
addresses, framebuffer/ramdisk and signed Stage65 PID1 remain pinned.

The initial Stage67 GitHub run `41594140727` silently skipped patch
`0101` (duplicated draw call) and consequently patch `0102`. That image
was invalidated and replaced; **do not flash the older SHA**.

Corrected kernel build `41617481649`, commit `c15a323`, completed
successfully. The workflow now fails if any of the required 0100–0102
patches are skipped, and its log proves all three were applied. The new
Mach-O was independently inspected and contains all ST67 VFS strings and
both PID1 bar messages. The kernel SHA256 is
`5fde9842617a904d5b5f75e2ca72be26d9f1c58840ff96afae54af4adc5721f7`.

The corrected Android boot-v2 image is
`shim/out/cactus/cactus-trace-stage-67-boot.img`, 45,541,376 bytes,
SHA256 `61677c867d9ee7abb4b7b42704201d8f3bd37929f88293053b19d21f67088bd2`.
Its relocated payload SHA256 is
`b1102efad550aba9cfa25c68fed0cea9d47563dc8f453bc4ee6be9d2181652c2`.
The kernel's native early-C entry moved to physical `0x81ac36bc`,
with join at `0x81ac3cec` and checkpoint at `0x81ac3d48`.
The static opcode/GIC/RAMDisk guard and all 16 USB decoder tests passed.
**This corrected Stage67 build has not yet been flashed.**

After hardware testing, compare the newest `ST67` markers and bar state.
If markers reach `ST67 BSD VFS returned`, investigate subsequent
`bsd_init()` initialization and its mountroot/PID1 bootstrap path.
