# Redmi 6A (cactus)

For the latest device test summary, open [Current Tests & Issues](../../docs/devices/cactus/current-tests-and-issues/README.md).

Verified on real hardware (Stage 85, 8 November 2026): native XNU, BSD initialization, mockfs executable loading, successful PID 1 `execve()`, EL0 SVC64 and the first PID 1 `getpid()` syscall. The native framebuffer's **PID1 RUNNING** indicator turned green. The prehandoff USB CDC trace and native framebuffer are separate evidence sources. See [Stage 85 hardware evidence](../../docs/devices/cactus/current-tests-and-issues/STAGE85-PID1-STACK-EXEC-FAULT.md). This is a minimal custom ARM64 userspace executable; dyld, launchd, SpringBoard and a functional iOS environment have not been verified.

The tested shim remains in [shim](../../shim/) and the [manifest](../../xnu/patches/manifest.json) tracks the ordered XNU patches. A flashable boot image requires locally generated and device-specific inputs in `shim/out/`. Preserve Stage 85 as the known-good baseline and never flash a cactus image to another device.

**November 8 Stage 87 update:** A real iOS 16 HFS+ root and original Apple
`launchd` execution reached PID 1 `getpid()` in Stage 86. Stage 87 now has
the expected `/dev` and other root paths, donor launch configuration and
the `sweetfb_noconsole=1` GUI handoff switch. Stage 87 was flashed and its
native XNU handoff observed over COM25; the new post-handoff framebuffer
result awaits the device owner's confirmation. The full iOS dyld shared
cache still requires an MT6765 eMMC-backed root and reliable donor
extraction. See [Stage 87 integration record](../../docs/devices/cactus/current-tests-and-issues/STAGE87-IOS-GUI-ROOT-INTEGRATION.md).

**November 8 Stage 88:** The Redmi 6A's MediaTek MSDC0 was accessed over
its inherited LK configuration at physical `0x11230000`: CMD13, CMD17 LBA1,
CRC-verified GPT, restored controller state and subsequent XNU handoff are
recorded in the COM25 capture. Stage88 is built and flashed; the kernel still
uses the Stage85/87 native XNU payload. The new
[read-only BSD eMMC driver patch](../../xnu/patches/devices/cactus/0121-cactus-msdc-readonly-root.patch)
has passed offline apply/manifest checks but needs a new XNU compile and
native device test. Genuine dyld/SpringBoard runtime remains incomplete.
See [Stage 88 record](../../docs/devices/cactus/current-tests-and-issues/STAGE88-SPRINGBOARD-FEASIBILITY.md).

**iOS 16 host filesystem staging:** All 44 iPhone 8 dyld arm64 cache files
were extracted and a 16 GiB HFSX diagnostic root containing genuine Apple
`launchd`, `dyld`, `SpringBoard`, launch configuration, and
SystemOS/AppOS cryptexes was built and independently read back. Source OS
extraction remains incomplete because APFS-FUSE failed on some resources.
No partition was overwritten and no new native XNU kernel was compiled
or flashed. See [the HFS staging record](../../docs/devices/cactus/current-tests-and-issues/IOS16-RUNTIME-HFS-STAGING-20261108.md).
