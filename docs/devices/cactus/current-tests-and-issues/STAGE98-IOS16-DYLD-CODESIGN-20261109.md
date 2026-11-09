# Stage98 — iOS 16 dyld shared-cache code signing compatibility

Date: 9 November 2026. Target: Redmi 6A cactus using the existing 16 GiB
iPhone X iOS 16.7.16 HFS+ root on `userdata`.

## Native evidence before this patch

Stage96 kernel + Stage97 userdata overlay reaches `exec launchd` and reports
`shared_region_check_np(...) vm_shared_region_start_address() failed`.
The XNU dyld shared region starts empty, so that message alone does not prove
failure: dyld may subsequently populate it via `shared_region_map_and_slide_2_np`.
No verified launchd-main, backboardd, SpringBoard, or Apple GUI exists yet.

## Integrated change

The iOS XNU build enables system code-signing enforcement by default. Its
standard `cs_enforcement_disable` boot argument only works if Apple's
`PE_i_can_has_debugger()` trusts `/chosen/debug-enabled`. The cactus boot shim
does not provide a signed Apple debugging environment.

Patch `0127-cactus-ios16-dyld-codesign-optin.patch` permits that explicit boot
argument on cactus while keeping the original rule on all other boards.
Stage98 boot arguments add `cs_enforcement_disable=1 cs_debug=1`, leaving the
tested Stage96 image unchanged. The new patch also logs the PID1 dyld cache
mapping syscall's entry counts and result, to distinguish the expected empty
initial check from an actual failed cache map.

Stage98 reuses Stage91's shim/eMMC/USB/display initialization, Stage96's
SHA-derived native opcode guard and Stage97's installed HFS+ root. Boot image
and kernel integrity are checked before device flashing.

## Verification and outcome

The patch passed manifest and source application checks. GitHub Actions run
`42597159586` completed successfully on `main` (`61c0b1c`). The compiled
Mach-O contains all three required Stage98 marker strings.

- Kernel: `kernel.development.cactus`, SHA256
  `454c51b43d2b94d0f6b973676b9cddacfb84b1790342694d3fd4c70e95e497b8`.
- Payload: `shim/out/cactus/payload-stage98.bin`, SHA256
  `029b2283efaa7d1fdd2b2596ad42d1d2475cbfb5b4c93c4ac6e0d1b61ed9924b`.
- Boot: `shim/out/cactus/cactus-trace-stage-98-boot.img`, 62,283,776 bytes,
  SHA256 `574d476e2da143bf761e99288be575d73f5e46ac06006e973d3cea7235f54743`.
- Stage98 packer checked the kernel SHA against CI SHA256SUMS, the 16 MiB
  fallback HFS digest, native layout, and all 41 inherited instruction guards.
  The boot image's independent checksum and device identity were checked
  before flash.
- Guarded fastboot of **boot only** succeeded against serial
  `3184a8a17d2b` reporting product `cactus`. `userdata` was not reflashed.
- Windows USB capture
  `usb-captures/stage-cactus-20261109-165010-144/session-001-165020-823.bin`
  has **91 valid frames, zero corrupt frames, zero gaps, zero duplicates**.
  Stage98 ordered `0x2303, 0x2800, 0x3500, 0x3900` confirms a verified
  kernel provenance marker `0x454c51b43d2b94d0` and native handoff.

The USB shim capture ends at native handoff; it does **not** establish that
the Stage98 code-signing boot argument was honored at runtime or that dyld
loaded the cache. A fresh native framebuffer log is required for the three
new `CACTUS IOS16` markers, Apple launchd main, and service startup.

**Apple GUI remains unverified until the screen actually displays SpringBoard.**
