# Redmi 6A (cactus)

Verified on real hardware: native XNU handoff, framebuffer and prehandoff USB CDC. PID1 userspace is unconfirmed. See [Stage79](../../docs/devices/cactus/STAGE79-MOCKFS-PID1.md). The tested shim remains in [shim](../../shim/) and the [manifest](../../xnu/patches/manifest.json) tracks its XNU patches. A flashable boot image requires locally generated and device-specific inputs in shim/out/. Never flash this image to another device.
