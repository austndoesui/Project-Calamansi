# Stage 53: compact native XNU boot console and BSD/startup visibility

**Status (2026-10-24): BUILT, FLASHED, NATIVE FRAMEBUFFER OUTPUT CONFIRMED.**
The USB prehandoff capture contains one missing trace frame, but the
owner's physical-screen transcription proves native XNU continued into
the early kernel/bootstrap and IOKit platform initialization sequence.
Root mount, BSD initialization and PID 1 are still unproven.

## What changes

Patch `xnu/patches/0090-cactus-startup-fbcon-stage53.patch` builds on
Stage52 patch 0089:

- CACTUS-only `FBCON_SCALE=1` renders native **8x16** glyphs (90 text
  columns x 90 rows on 720x1440). SWEET retains scale 2.
- A reserved seven-row Cactarwin/Redmi 6A header stays on screen while
  framebuffer log lines wrap through the remaining rows.
- A live `STATUS` line reports native bootstrap phases; XNU's
  `startup_debug` is set to `STARTUP_DEBUG_VERBOSE` on CACTUS.
- Additional native Mach IPC, startup-thread, and BSD-init checkpoints
  expose progress beyond Stage52's last reported messages.
- Stage49 physical OVL0 layer1 guard, Stage50 boot-args redirect,
  Stage51 early framebuffer table/ADT fix, Stage52 persistent console,
  COM serial prehandoff and XNU exception capture remain included.

Stage51 physically displayed XNU's `kprintf startup complete` message;
Stage52's on-device serial prehandoff passed and native framebuffer logs
were observed extending into Mach IPC. Full kernel boot, root mount and
userland PID 1 are **not yet proven**.

## Verified build provenance

- Source branch: `stage53-cactus-progress`; committed small-font
  update `283dbee`, pushed to `austndoesui/Cactarwin`.
- Cactus XNU GitHub Actions run `40111491409`: **SUCCESS**.
- Mach-O: `../stage53-kernel-smallfont-run40111491409/kernel.development.cactus`
  (17,158,168 bytes), SHA256
  `361846aab01f80408e087e37527d774cc63766797d028bc7d701ec298a50a09e`.
- Packed payload: `shim/out/cactus/payload-stage53.bin`, SHA256
  `824461ebd957b2bbba4349b9687c7318ac298785e0510ce021946ceef92d685b`.
- Relocated payload:
  `shim/out/cactus/linux-chainload/stage53-relocated-payload.bin`
  (16,557,168 bytes), SHA256
  `e00468ddf5434f70205b9e1aa0fcb26d2e2f967a1660dc858bfb6cf8c903cbaf`.
- XNU physical entry `0x8142d488`; native C entry `0x81ac28fc`;
  C branch checkpoint `0x81ac2f2c`; post-init guard `0x81ac2f88`.
  `shim/check_stage53_xnu.py` pins the exact binary instructions,
  entry, MMU/bootstrap vector, ADT and LK framebuffer reservation.

**Flashable Android boot v2 image:**
`shim/out/cactus/cactus-trace-stage-53-boot.img`
(45,524,992 bytes), SHA256
`a6601e7f5264139c21c71bd9513e3175a6d3876a46f1ff0e53a498432607990c`.

Offline: boot header/DTB verified; Stage53 static guard **PASS**;
**42** Ubuntu shim unit tests **PASS**, shell syntax and Python compilation
**PASS**. XNU linker warns about the existing shim ELF RWX load segment.

## Hardware test once cactus fastboot is connected

```powershell
fastboot devices -l
powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1' -Stage 53 -CaptureSeconds 105
```

The existing runner confirms serial, product=`cactus`, image SHA,
flashes boot, reboots and starts the COM capture before reboot.
Decode the saved binary session with
`python shim/decode-cactus-usb.py "CAPTURE.bin" --require-stage53 --show 100`.
The `0x5300` marker verifies prehandoff, not native XNU output.
Record the **last visible XNU line**, particularly whether BSD or
root-mount initialization begins. Native video and COM logging are
different output paths after the handoff.

### Stage53 device trial, ~22:22 local

The guarded `run-stage49.ps1 -Stage 53 -CaptureSeconds 105`
verified the connected fastboot device, boot image and product, then:

- `fastboot flash boot`: OKAY (1.480s sending, 0.606s writing).
- `fastboot reboot`: OKAY.
- COM25 enumerated and recorded **4,368 bytes** to
  `../usb-captures/stage-cactus-20261024-222228-785/session-001-222239-782.bin`.
- Decoder found **78 valid frames**, zero bad/noise/duplicates/regressions,
  but **one missing sequence (64)**, between the `0x5300` handoff
  context and later watchdog keepalive samples. The strict
  `--require-stage53` verdict is **INCOMPLETE**, not PASS.
- Stage53 events `0x4802`, `0x4900`, `0x4901`, `0x4902`,
  `0x5000`, `0x5100`, `0x5300`, `0x2303`, `0x2800`,
  `0x3500` and `0x3900` are physically present with matching
  PA/opcodes/identity. Native XNU progress after handoff cannot be
  inferred from them.
- Runner exited with `No COM25 frames captured` even though the
  watcher log proves the recorder opened COM25, wrote 4,368 bytes,
  and closed normally. This is a runner file-discovery/timing issue,
  **not** evidence that the flash failed.

### Stage53 actual framebuffer evidence (owner, ~22:45 local)

Full owner-provided transcription:
`../../xnufboutput.txt` (4,478 bytes, 81 lines). It physically displays
the compact Cactarwin header and `Darwin Kernel Version 22.6.0` from
`xnu-8796.141.3`, followed by successful pmap/VM startup messages,
scheduler quantum setup, Mach IPC table initialization
(`mach_kobj_count = 374`), security policy registration and various
inherited SWEET IOKit service messages.

The persistent header's last visible status was transcribed as
`STATUS PE_lockdown_lockit`. The exact XNU source marker at this
location is **`PE_lockdown_iokit`**; the transcription has several
other obvious text errors, so treat this spelling as approximate.
The local XNU `osfmk/kern/startup.c` prints the marker immediately
**before** calling `PE_lockdown_iokit()`. The implementation in
`pexpert/arm/pe_init.c` calls `zalloc_iokit_lockdown()` then
`StartIOKitMatching()`. Once it returns, startup calls
`vm_set_restrictions(machine_info.max_cpus)` and then `bsd_init()`.
No later STATUS value or `bsd_init enter` is visible in this capture:
**we cannot yet tell whether IOKit lockdown/matching blocked, faulted,
or simply ceased writing to the framebuffer**. The `gPanicBase ... not
initialized` warnings occurred earlier and execution continued past
them; they are not established as the stopping cause.

The transcription also ends with `SWEET CPU: requested=1 selected=1
(limit=0)`, a value worth verifying against the actual compiled
runtime and `machine_info.max_cpus` before interpreting it as a bug.

Stage54 should add separate, safe native framebuffer checkpoints
immediately before/after the two IOKit calls and before/after
`vm_set_restrictions` and BSD entry; see
`shim/TRACE-STAGE54-PLAN.md`. Avoid bypassing genuine kernel
initialization merely because the last status did not advance.

## iOS 16 userland dependency

Stage53 carries the XNU Mach-O as a shim payload, not an iOS filesystem.
The inherited `tools/mkpayload.py --ramdisk` and
`tools/sweet-init.S` can form a source-generated diagnostic
`/sbin/launchd`/PID 1 when root mounting is reached. The local
`xnu_device_benesse_a04br3` reference also has
`tools/a04br3-init.S`, `mkinit.py`, `mkhfsroot.py` and HFS+
bring-up evidence on its **own** MTK tablet. Hardware addresses,
page sizes, partition layout and any eMMC write procedure require
separate Cactus validation.

For subsequent *Apple dyld* experiments the Benesse instructions select
the **iPhone X (iPhone10,3 / iPhone10,6) iOS 16.7.16 build 20H392 restore
IPSW**, extracting original OS dyld and Cryptex shared caches. That IPSW
is not needed for Stage53 or for the first source-built static PID 1.
See `docs/CACTUS-USERLAND-PLAN.md`.
