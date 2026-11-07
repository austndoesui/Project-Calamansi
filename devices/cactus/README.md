# Redmi 6A (cactus)

Verified on real hardware (Stage 85, 8 November 2026): native XNU, BSD initialization, mockfs executable loading, successful PID 1 `execve()`, EL0 SVC64 and the first PID 1 `getpid()` syscall. The native framebuffer's **PID1 RUNNING** indicator turned green. The prehandoff USB CDC trace and native framebuffer are separate evidence sources. See [Stage 85 hardware evidence](../../docs/devices/cactus/STAGE85-PID1-STACK-EXEC-FAULT.md). This is a minimal custom ARM64 userspace executable; dyld, launchd, SpringBoard and a functional iOS environment have not been verified.

The tested shim remains in [shim](../../shim/) and the [manifest](../../xnu/patches/manifest.json) tracks the ordered XNU patches. A flashable boot image requires locally generated and device-specific inputs in `shim/out/`. Preserve Stage 85 as the known-good baseline and never flash a cactus image to another device.
