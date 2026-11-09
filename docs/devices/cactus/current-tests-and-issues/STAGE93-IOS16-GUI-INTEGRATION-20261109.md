# Stage93 — integrated iOS 16 Apple userspace / GUI bring-up

Date: 9 November 2026. Target: Xiaomi Redmi 6A (`cactus`), XNU-8796,
iPhone X iOS 16.7.16 (`20H392`). Device-specific evidence; no claims for
other Project Calamansi targets.

## Hardware checkpoint inherited from Stage92

User's native framebuffer transcription `fulldump.txt` confirms:

```
SWEET FB: AppleCLCD ... presented as 1125x2436
CACTUS MSDC: block open dev=2:1 expected=2:1 ... error=0
hfs: mounted LOSRoot on device b(2, 1)
shared_region: ... vm_map_enter (0x100000000,0x100000000,...) error 0x4
exec launchd
```

The external iPhone X HFS+ root mounted successfully on eMMC userdata.
`exec launchd` indicates XNU attempted Apple's init program; it does not
prove launchd reached `main`, spawned backboardd, or rendered SpringBoard.
The shared-region error needs correlation with actual userspace behavior;
earlier minimal PID1 runs survived a similar message.

## One consolidated integration build

Patch `xnu/patches/devices/cactus/0124-cactus-ios16-gui-bringup.patch`
reuses the inherited ios-sweet kernel IOSurface (`IOCoreSurfaceRoot`),
`IOMobileFramebuffer`/`AppleCLCD`, software CoreAnimation scanout,
AppleKeyStore, HID, sandbox, crash logs and service trace facilities.

The patch updates the touch driver's 1080x2400 Sweet geometry to the boot
panel dimensions (720x1440 on cactus), with an iPhone X logical screen
(1125x2436). It starts the existing process sampler from the native HFS
boot path, watching launchd, backboardd, SpringBoard and mobileactivationd
every ten seconds beginning five seconds after init, and prints when
Apple launchd sets `kern.initproc_spawned=1`.

`tools/stage93_pack_kernel.py` and `shim/build_trace_probe.sh 93` package
a new SHA-verified DEVELOPMENT kernel using Stage91's known-good native
GIC, framebuffer, MSDC, fallback HFS, and USB handoff. The 16 GiB iPhone X
userdata image remains installed without re-extraction or re-flashing.

## Result — CI skipped the integration patch

CI run `42576739043` completed and the kernel was packaged/flashed, but the
build log reported `Skipping patch ...0124-cactus-ios16-gui-bringup.patch`
because its `bsd_init.c` hunk did not match the fully patched source. The
compiled kernel retained the old Sweet HID string and lacked the new
`CACTUS IOS16` markers. The hardware's unchanged framebuffer is therefore
expected. Stage93's 91 valid COM25 frames confirm only pre-XNU handoff.
The corrected patch and CI fail-closed checks are tracked in [Stage94](STAGE94-IOS16-DYLD-SHARED-REGION-20261109.md).

## Evidence requirements

- Build the complete 0124 patch stack for `CACTUS` on the macOS CI toolchain.
- Verify kernel hash, entry, executable mapping, Apple device tree,
  fallback HFS, root selection, and the Stage91 shim handoff before flashing.
- Check the device serial/product at fastboot before boot flashing.
- Record actual framebuffer progress to determine whether Apple launchd
  reaches `main` and spawns services. Apple logo/SpringBoard graphics are
  only verified if observed on device.

Stage93 build/flashing outcomes must be appended from actual command output
and hardware results; no untested claim of an iOS GUI boot belongs here.
