# Stage 80 — Calamansi live event console and minimal PID 1 Mach-O guard

## Source and scope

- Calamansi XNU patch: xnu/patches/devices/cactus/0115-cactus-calamansi-console-pid1.patch.
- The framebuffer is backed by native XNU pe_serial, not the host COM25 watcher.
- It now brands the panel Calamansi, reserves twelve ordered recent-event lines,
  keeps the most recent event and last failure visible in a fixed bottom panel,
  and confines ordinary serial output to the region above it.
- Existing amber PID1 waiting bar and green only-on-syscall behavior remain.
- PID1 executable read still follows the normal vn_rdwr and XNU Mach-O loader.
  The new guard checks a minimum 32-byte Mach-O header and MH_MAGIC_64
  before invoking the normal image activator; malformed PID1 gets EBADEXEC.
  This is a minimal validity check, not a bypass of code signing or loader rules.
- Post-vnode-read/higher vn_rdwr completion and PID1 userspace execution are
  unconfirmed pending a native on-panel test.

## Build

- Commit 20699a7 pushed to Calamansi main.
- GitHub Actions run 42382619097 completed successfully, with all Stage80
  source patches applied. Kernel SHA256
  af41e570707774fb9217a40db32f42ac2ea180c9901049ccc7902c2035b2905e.
- Relocated payload checksum:
  ae324787bc76f8ba98ec9cea0adaf94b001113dafc0be4a29e9f1e733c5026cc.
- Kernel entry physical 0x8142c488, Stage80 native C prologue physical
  0x81abf4cc, pinned checkpoint 0x81abfafc, RAMDisk physical 0x824b8000,
  boot_args physical 0x824c4000. All 41 kernel opcode/boot-layout guards pass.

## Physical test and corrected image

- First Stage80 image SHA256
  f397bb75e434baaab75c2ec7e5c9b778d11c051ca97a7e611f1eb680f7618c6f
  successfully flashed to cactus, but its prehandoff COM25 trace reported
  status 0x510 from stage20b_arm. That trace was 55 valid frames with
  zero corrupt frames and zero sequence gaps. No native XNU handoff occurred.
- Deterministic cause: Stage80 boot_args moved to 0x824c4000 while the
  stage20b_arm guard still required 0x824c0000. This was corrected under
  CACTUS_STAGE80_NATIVE in shim/stage19_probe.c. No XNU rebuild was necessary.
- Corrected, offline-built Stage80 image:
  shim/out/cactus/cactus-trace-stage-80-boot.img
  SHA256 b9fc64323abf1a71913162254e5696064f4bf8df28868225d47ba7f1919c4ec0,
  size 45,522,944 bytes. Boot v2 header, payload SHA and 41 pinned
  instructions passed.
- After this rebuild, fastboot devices and adb devices returned no device.
  **Corrected image has NOT been flashed or tested on hardware.**
  When cactus re-enters fastboot, verify product/serial before using
  shim/run-stage49.ps1 -Stage 80 -Serial <device_serial> -CaptureSeconds 60.
- Existing known-good Stage79 image and rollback assets have not been
  overwritten in version control.

## Corrected hardware replay

- The corrected Stage80 image SHA256 b9fc64323abf1a71913162254e5696064f4bf8df28868225d47ba7f1919c4ec0 was subsequently flashed to a fastboot-identified cactus, product verified.
- COM25 file: usb-captures/stage-cactus-20261107-203850-078/session-001-203859-163.bin. 80 valid frames, zero corrupted, 10 missing sequence numbers. Stage80 identity event 0x2800 and real native handoff 0x3500 both present; 0x510 guard regression resolved.
- Physical screen reports ST79 mockfs devread finished as latest visible STATUS, preceded for approximately 100 seconds by ST56 CPU all initialized (user-reported visual timing, not measured in native logs).
- A Stage80 console implementation error was subsequently found: the message pointer was advanced by STATUS rendering before the recent-events ring recorded it, leaving event history empty. A separate Stage81 patch fixes this.
