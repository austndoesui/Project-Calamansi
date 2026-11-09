# Stage96 — iOS 16 dyld shared-region 4 KiB mapping (9 November 2026)

Stage95 confirmed native mounting of the iPhone X `20H392` HFS root from
userdata, the GUI HID/AppleCLCD code, and `exec launchd`. Native XNU reported
`KERN_INVALID_ARGUMENT (0x4)` both with nested and flat dyld shared-region
mapping. SpringBoard and Apple launchd main remain unverified.

## Functional change

XNU `vm_shared_region_create()` defaulted a 64-bit submap to 16 KiB alignment
while cactus EL0 tasks use 4 KiB. The `vm_map_enter()` code rejects a named
submap whose page shift differs from the target task, returning error `0x4`.
Removing the nesting flag leaves that mismatch intact.

Patch `0126-cactus-ios16-shared-region-4k-pages.patch` selects the matching
4 KiB shift for the cactus ARM64 shared submap and reports both shifts at
runtime. The patch applies to the exact CI patched source. The manifest and
CI checks require that it applies and that its compiled marker is present.
The page-shift mismatch is a source-grounded candidate cause; the on-device
result of this functional change awaits native framebuffer confirmation.

## Build and hardware

- Commit: `a590a072bf87f32dc32a3069358dcb1f80af4b80`.
- CI run `42585942887`: SUCCESS; kernel SHA256
  `e59222f3651de828366dda3af774e845ec52598ec6e9626c598c0580df1b403c`.
- Stage96 payload SHA256
  `6fd8c2a4a8a2f9cf97c93c95c5d6e6048384d250a3885a4d521928a16bcf7037`.
- Image `shim/out/cactus/cactus-trace-stage-96-boot.img`:
  62,283,776 bytes; SHA256
  `50c949f25607f1f5d4375ec2bc42df99d6e5d676c9c48c21127b993383610a80`.
- The Stage96 validator checked kernel SHA256SUMS, five instructions
  against the Mach-O and relocated payload, plus 41 original root/ADT/GIC/
  framebuffer/boot guards. It generated matching C shim pins.
- Guarded fastboot flash to confirmed `3184a8a17d2b` / `cactus` succeeded.
  Only boot was flashed; the 16 GiB iOS userdata remains installed.
- COM25 `usb-captures/stage-cactus-20261109-140456-560/session-001-140508-091.bin`
  contains 80 CRC-valid frames, zero corruption, but 11 missing sequence
  numbers (64–74). Thus the strict full capture reported incomplete.
  Ordered `0x2303`, `0x2800` with kernel prefix `0xe59222f3651de828`,
  `0x3500` native XNU handoff, and `0x3900` were captured.

**Next evidence:** A native framebuffer log indicating
`CACTUS IOS16: dyld map page shifts task=12 submap=12`, the mapping result,
and Apple `launchd`, `backboardd` or SpringBoard startup. USB trace alone
cannot establish Apple userspace or GUI boot. The green PID1 bar reflects
the earlier minimal EL0 syscall milestone.
