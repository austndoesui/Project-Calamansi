# Stage94 — native iOS 16 launchd/dyld recovery

Date: 9 November 2026. Target: Redmi 6A cactus and the existing iPhone X
iOS 16.7.16 build 20H392 HFS+ image on userdata.

## Why this stage exists

Stage93 CI silently skipped the entire service/geometry patch. Its kernel
compiled but did not contain any new iOS16 integration code. The last native
framebuffer still proves successful eMMC block open and HFS `LOSRoot` mount,
followed by `exec launchd` and a dyld shared-region VM mapping failure
(`KERN_INVALID_ARGUMENT`, 0x4). No launchd-main or SpringBoard GUI yet.

## Combined corrections

1. Patch `0124` now applies to the **actual post-0123 CI XNU source**, whose
   `bsdinit_task` includes earlier cactus framebuffer progress calls. This
   enables cactus touch-panel geometry, iOS service process sampling, and the
   `kern.initproc_spawned` launchd-main marker that Stage93 intended.
2. Patch `0125` provides a narrowly scoped cactus ARM64 fallback for the
   failing nested dyld shared-region mapping. It retries the same mapped
   object at the same fixed address with ordinary page-table mapping when
   `vm_map_enter_mem_object` rejects pmap nesting with error `0x4`. It reports
   the second result and leaves other error paths unchanged. This is a
   hypothesis based on the native framebuffer and needs a hardware test.
3. CI now requires `0122` through `0125` to be applied and checks for four
   integration strings **inside the compiled XNU Mach-O**. It must fail if
   a patch is silently skipped or the expected implementation is absent.
4. Stage94 packages the pinned CI kernel as a distinct image using the
   known-good Stage91 shim, GIC, USB, fallback HFS, eMMC root and framebuffer
   guards. It does **not** rewrite or reflash the 16 GiB userdata filesystem.

## Validation and device outcome

Source patches applied to the archived exact Stage93 CI source without
conflicts, and `git diff --check` passed on the resulting C/C++ files.
Patch manifest verified (`127` files, `124` patches). Git commit:
`11aff72650e42fd3ba7f74af6583c35ccc89420b`.

CI, kernel checksum, built image checksum, guarded fastboot result, USB
capture, and on-screen Apple userspace results should be recorded here after
each completes. Apple GUI is **not yet verified** by this document.

Hardware follow-up: Stage94 flashed but hit a stale shim instruction guard
(0x510) before native handoff; 56 valid pre-XNU USB frames. [Stage95](STAGE95-SHIM-GUARD-CORRECTION-20261109.md)
fixed that guard and confirmed native XNU handoff with 91 valid frames. The
next actual framebuffer still showed both shared-region mapping modes
returning 0x4. [Stage96](STAGE96-IOS16-DYLD-4K-SHARED-REGION-20261109.md)
addresses the mismatched XNU shared-submap page shift.
