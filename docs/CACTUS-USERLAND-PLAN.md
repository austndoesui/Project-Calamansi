# Cactus XNU to iOS 16 userspace: available components and next boundary

**Current proof (2026-10-24):** Stage54 XNU and boot image were compiled,
packed and verified offline. Hardware trial has not run yet. The downloaded
iPhone X IPSW matches iOS 16.7.16 build 20H392 and includes the d22ap
OS (`087-86698-044.dmg`) and SystemOS Cryptex
(`087-86593-047.dmg`); no Apple files were extracted. This does not
advance the demonstrated userspace boundary. Redmi 6A physically executed Stage53 XNU
and displayed its 8x16 framebuffer console. The owner-provided 81-line
screen transcript in `../../xnufboutput.txt` shows VM bootstrap, Mach IPC
and IOKit platform services. The latest persistent header status corresponds
to `PE_lockdown_iokit` immediately **before** the call. No Cactus
`mountroot`, executable PID 1, Apple dyld, launchd, or SpringBoard run
has been demonstrated.

## Reuse in this repository

| Existing file | Purpose | Cactus validation |
| --- | --- | --- |
| `tools/mkpayload.py` | `--ramdisk` appends a root image and ADT RAMDisk data; `rd=md0` selects it. | Adapt to the Stage53 packer and prove reservation, bounds and root selection. |
| `tools/sweet-init.S` | Source-built diagnostic Mach-O in place of `/sbin/launchd`. | Verify ABI, codesigning policy, entry and console output on Cactus. |
| `tools/mkiosroot.sh` | Reconstructs an iOS donor OS/Cryptex file tree. | Host-side only until filesystem/launch path works. |
| `xnu/patches/00xx-sweet-*.patch` | Existing filesystem, IOKit, sandbox, AppleKeyStore and service compatibility work. | Audit assumptions; do not infer that every iOS 16 service boots on MT6761. |

The adjacent cloned `xnu_device_benesse_a04br3/xnu_device_benesse_a04br3`
project offers a more targeted **MTK** reference:
`tools/a04br3-init.S`, `tools/mkinit.py`,
`tools/mkhfsroot.py`, `tools/prepare-dyld-root.py`, and
`tools/build-dynamic-probe.sh`. Its README records an actual HFS+ and
diagnostic PID 1 hardware boot on TAB-A04-BR3 (2026-10-20).
Its bootstrap memory maps, 16 MiB boot-partition limit, storage driver,
kernel flags and pointer conventions must **not** be copied onto Cactus.

## Fastest useful milestones

1. **Stage54**: instrument `PE_lockdown_iokit` around
   `zalloc_iokit_lockdown()` and `StartIOKitMatching()`, then the
   `vm_set_restrictions`/`bsd_init` boundary. Record both `STATUS` and
   native framebuffer scroll output, and distinguish an actual kernel
   fault from silent console stalls. Do not skip the real IOKit matching
   process just to print a later status.
2. **Stage55 diagnostic userland**: currently built offline alongside BSD-gate
   diagnostics; the Stage54 screen proves VM restrictions complete. The static
   Cactus ARM64 Mach-O, pinned in-memory root segment and `rd=md0` ADT
   were verified in the Stage55 image; **no physical root/PID1 run yet**.
   During the hardware trial, after confirming the BSD/root path,
   wire an in-memory `rd=md0` root to
   the current payload/ADT, with a **source-generated static diagnostic
   PID 1**. Verify a PID-1 banner and heartbeat without depending
   on proprietary Apple binaries or working eMMC. Prepare the root
   packer and executable in parallel with Stage54 source debugging.
3. Introduce a small test HFS+ root and prove regular-file reads and
   process launch; only then move toward Apple dyld and iOS services.
4. Extract matching original dyld/shared-cache files from a user-supplied
   donor IPSW, confirm minimal dynamically linked process creation,
   then evaluate launchd and other services separately.

**When to download the IPSW:** It can be downloaded now in parallel
for the later dyld stage, but there is no need to unpack it to test
Stage53 or a static PID 1. The tested Benesse README specifies an
**iPhone X iPhone10,3/iPhone10,6 iOS 16.7.16 (20H392) restore IPSW**,
with `BuildManifest.plist` identity `d22ap`; that is a reference for
donor extraction, not proof it will boot unmodified on the Redmi 6A.
Keep donor firmware images and Apple binaries outside the source repo.

**Critical remaining gap:** Cactus's 4 KiB hardware MMU granule,
experimental 16 KiB XNU software VM pages, real LK framebuffer and
MTK eMMC are not the Benesse device configuration. A native XNU
console milestone does not establish working root mounting or iOS
16 userspace.

Detailed near-term acceptance checks: `../shim/TRACE-STAGE54-PLAN.md`.
