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

The patch must pass manifest validation, apply against the current CI XNU
source, compile into a SHA-verified Mach-O (including required marker strings),
and be packaged with verified native instruction pins before flashing.

**Apple GUI remains unverified until the screen actually displays SpringBoard.**
