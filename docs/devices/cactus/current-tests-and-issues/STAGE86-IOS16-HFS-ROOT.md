# Stage 86 — iOS 16 HFS+ root and guard fix (2026-11-08)

## Payload

- iOS donor: iPhone 8 iOS 16.7.16 (20H392), source IPSW in the project root.
- 16 MiB HFS+ ramdisk: `_build/ios16-runtime/stage86-guestfs.hfs`; SHA256 `1a64ae893082d3def930dba358c28c2a3a5b51b98b465152479144431666c68a`.
- Contains extracted Apple ARM64 `/sbin/launchd`, `/usr/lib/dyld`, SpringBoard executable, and launch plist. Does **not** yet contain dyld shared-cache subcaches, libSystem, libobjc, or SpringBoard frameworks.
- Preserves Stage 85 XNU kernel SHA256 `dd39a64cd43de54dd79a2eaabb23b3e689a242179baccdf6399c93aad1da13fc` and native-entry opcode pins.

## First hardware attempt and deterministic guard failure

- Original Stage 86 image `cactus-trace-stage-86-guardfail-boot.img`, SHA256 `652f3b031fbd1fbcf0494f31ed46d1db9e4d6850fd486d3311a9221f646ec099`.
- Fastboot flash on verified cactus serial succeeded. COM25 trace `_build/stage86-captures/stage-cactus-20261108-025031-769/session-001-025050-308.bin`: 56 valid frames, status `0x510`, no `0x3500` handoff.
- Root cause: 16 MiB ramdisk moved `boot_args` to physical `0x834bc000`, while `stage20b_arm()` retained Stage 80+ fixed expected address `0x824c4000`. This is the same failure class documented for Stage 80.

## Corrected build and hardware test

- Added `CACTUS_STAGE86_NATIVE` only for Stage 86 and pin its expected `boot_args` address to `0x834bc000`; unchanged Stage 85 kernel instruction pins and entry validation.
- New `shim/out/cactus/cactus-trace-stage-86-boot.img`, size 62,283,776 bytes, SHA256 `97bfbf9f4888ea5544df777e9de31ab6f8c51224d0432b84fb1bd1920b193040`. Fits verified 64 MiB boot partition. Build and offline image/ramdisk/ADT validators passed.
- Flashed after checking fastboot `product: cactus` and serial `3184a8a17d2b`. Boot write/reboot OKAY.
- COM25 `_build/stage86-guardfix-captures/stage-cactus-20261108-025640-477/session-001-025658-922.bin` confirms Stage 86 `0x2800` native kernel identity and **`0x3500` native XNU handoff** with entry PA `0x8142c488`, boot_args PA `0x834bc000`. The earlier `0x510` guard failure is resolved.
- This is a prehandoff trace. It does not prove successful HFS+ mount, dyld, launchd, or SpringBoard. Hardware visual status and first native failure remain to be established.

## Next blocker

- Verify actual XNU HFS+ mountroot and launchd startup using framebuffer/panic output. The existing `mockfs_check_macho` is intended to decline a non-Mach-O block root and allow the real filesystem driver to attempt mountroot; HFS+ presence in the binary alone is insufficient to establish a working mount.
- iOS 16 launchd needs `/usr/lib/dyld` plus libSystem.B.dylib and libobjc.A.dylib, and modern dyld shared cache/VM/Mach services. SpringBoard needs additional frameworks and Apple services.
- Stage 85 known-good boot image SHA256 `5d43ed73c067ada0dbff5ec98776ddf8b7c99435386a8fddbe93552ad8efe53c` is retained unchanged.

## Real iOS launchd platform rejection and targeted boot-arg revision (2026-11-08)

- After the original corrected Stage86 reached native XNU, the physical screen reportedly showed `ST84 PID1 task switch done`, followed by `unexpected sigkill of launchd (cs_killed)` with OS reason namespace **9**, code **0xe**. In the pinned XNU source (`bsd/sys/reason.h`), this is `OS_REASON_EXEC` / `EXEC_EXIT_REASON_WRONG_PLATFORM`, **not** the code-signing namespace (`3`).
- The XNU macOS-target exec path (`bsd/kern/kern_exec.c`, near the `mac_proc_check_launch_constraints` call) explicitly rejects `PLATFORM_IOS` executables when a spawn platform is not provided and the development-only `unentitled_ios_sim_launch` tunable is false. The actual iPhone 8 donor `/sbin/launchd` has `LC_BUILD_VERSION platform=2` (`PLATFORM_IOS`). This is a concrete platform-policy mismatch; the panic string's `cs_killed` alone does not identify its reason.
- The Stage85 development kernel embeds `unentitled_ios_sim_launch` and supports boot-arg `unentitled_ios_sim_launch=1` under `DEBUG || DEVELOPMENT`. Enabled **only in the Stage86 packed XNU command line**, without changing the XNU kernel or HFS+ root. The payload validator now checks this exact command line and retains native entry, ADT, RAMDisk and opcode pins.
- Archived the prior handoff-successful, launchd-platform-failing boot image as `shim/out/cactus/cactus-trace-stage-86-before-platform-fix-boot.img`, SHA256 `97bfbf9f4888ea5544df777e9de31ab6f8c51224d0432b84fb1bd1920b193040`.
- New Stage86 image: `shim/out/cactus/cactus-trace-stage-86-boot.img`, SHA256 `fdc9b9f781e79d3c6121a2321f06aea76c9ca62d4906df274e6c887cc38257cb`, size 62,283,776 bytes. Offline image, exact command-line validator, and patch-manifest checks passed.
- Flashed on verified `cactus` serial `3184a8a17d2b` with watcher running. Fastboot flash/reboot OKAY. COM25 `_build/stage86-platform-fix-captures/stage-cactus-20261108-110933-231/session-001-110943-897.bin` captured **91 valid frames, 0 corrupt, 0 gaps**, including identity `0x2800` and XNU handoff `0x3500` with `boot_args` at `0x834bc000`.
- At flash time, the post-handoff native screen outcome was unverified; the COM25 trace stops at handoff. The **subsequent owner-reported framebuffer result is documented below**. Dyld cache and other userspace dependencies remain blockers.

## Hardware framebuffer update: real HFS root and first PID 1 syscall

After the development boot-arg revision, the device owner reported the native framebuffer showing:

- `SWEET HFS: hfs-627.188.6 registered`, `BSD root: md0`, and **`hfs: mounted untitled on device b(1, 0)`**. This confirms real HFS+ root mounting, beyond the Stage85 mockfs PID 1 proof.
- `exec launchd`, `SWEET Sandbox: Launchd op 2`, then `ST84 PID1 signature done`, `ST71 PID1 execve ok`, `ST71 PID1 exec accepted`, and `ST68 PID1 exec returned`. The earlier EXEC/WRONG_PLATFORM panic is absent in this observed boot.
- **Green `PID1 RUNNING - user syscall verified`** with `ST85 EL0 ec=15 esr=56000080 ... pc=10122679c`. The unchanged Stage85 getpid hook in `bsd/kern/kern_prot.c` turns green only when process 1 actually calls `getpid()`. Stage86 therefore reached genuine process-1 EL0 and its first syscall with the Apple dynamic launch chain present. This does not yet prove that launchd's main routine or service startup executed; the syscall could originate in dyld startup.
- The trace also records EL0 instruction abort (`ec=20`, `esr=82000007`, `far=101233c00`) and data abort (`ec=24`, `esr=92000007`, `far=10128ecb0`) *before* the successful syscall. These faults were not immediately fatal; the Stage85 exception probe reports only the first occurrence of each class.
- Observed `devfs_kernel_mount: kernel_mount failed: 2` (ENOENT). Offline read-only guestfish inspection of the exact HFS+ image confirms root contains only `/System`, `/sbin`, `/usr` — **no `/dev` directory**. The next root revision should add `/dev` and necessary standard writable mount-point directories before drawing conclusions about devfs.
- Observed `shared_region: enter ... vm_map_enter(...) error 0x4` (`KERN_INVALID_ARGUMENT`); its impact on subsequent dyld cache mapping must be diagnosed, not assumed to be a fatal panic. Real `launchd` requires `/usr/lib/libSystem.B.dylib`, `/usr/lib/libobjc.A.dylib` and iOS 16 dyld shared cache; the 16 MiB ramdisk has only the dyld binary, launchd, SpringBoard executable and SpringBoard plist.

**Interpretation:** This is live native XNU plus HFS+ root mount and a genuine PID 1 system call. It is not yet a full iOS boot, SpringBoard launch, or graphical Apple boot logo. Next stage should pair a correct root directory layout with dyld cache/library mounting and targeted loader/launchd checkpoint instrumentation. Avoid further repeated flash-only tests unless they answer a specific identified blocker. The Stage85 hardware-proven recovery baseline and both Stage86 images remain preserved.
