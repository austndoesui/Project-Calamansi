# Stage100 — late virtual-timer recovery during Apple launchd startup

Date: 9 November 2026. Device: Redmi 6A (cactus), MT6765.

## Verified baseline

Stage99 built and was flashed; the pre-XNU COM25 handoff was verified.
Native framebuffer logs in recent runs show the iPhone X HFS+ `iOSRoot`
mounted, `exec launchd`, and `SWEET Sandbox: Launchd op 2`. The Stage85
green PID1 indicator only proves the earlier minimal EL0 syscall test.
Apple launchd main, `backboardd`, SpringBoard, and the real iOS GUI have
not been demonstrated.

The missing five-second process-sampler wakeup may indicate virtual-timer
interrupt or timed-wait delivery trouble. This is a **hypothesis**: the
available framebuffer trace does not distinguish a blocked sampler from
lost console output. The `check_np` shared-region message can occur while
dyld is establishing its first shared-cache mapping.

## One combined functional patch

- `0129-cactus-ios16-late-virtual-timer-recovery.patch` restores
  `CNTV_CTL_EL0.ENABLE` and clears `IMASK` only if the register unexpectedly
  changed when XNU programs the next virtual-timer deadline.
- At platform initialization, read hardware `CNTFRQ_EL0` if within a
  plausible range, so timebase/decrementer conversion uses the running
  counter. The cactus ADT's advertised 13 MHz already matches earlier
  shim checks.
- On Apple's real PID1 sandbox operation 2, recheck the CPU0 GICR PPI27
  enable path in addition to the previously added process-sampler check.
  This path executes even when the sampler never wakes.

Do not interpret a `ST100 late PPI enabled` status as proof that the timer
interrupt is delivered. For that, require the existing `ST99 timer IRQ and
wait OK` status and actual service process sightings.

## Acceptance criteria

1. Ordered patch SHA manifest, zero-fuzz apply against Stage99 CI source,
   native instruction guards, and compiled Stage100 markers pass.
2. Guarded cactus fastboot flash and pre-XNU handoff are observed.
3. Native screen shows `ST99 timer IRQ and wait OK` or concrete timer
   failure evidence, then Apple launchd main and service startups.
4. The milestone requested by the owner is actual SpringBoard GUI on
   the panel, not merely the static XNU framebuffer or a green PID1 bar.

Stage97 HFS+ userdata and the known working Stage99 boot image are left
unchanged by source preparation.

## Build and attempted hardware test

- Pushed source commit `fdf28bb` to `main`. GitHub Actions run `42660810594`
  compiled successfully with all required XNU patches and Stage100 markers.
- CI kernel SHA256:
  `feda1f3cf6cac00fea6dab35bbaec508a00117c2c418c4c81798baf3da3c9904`.
- Packaged payload `shim/out/cactus/payload-stage100.bin`, 33,316,880 bytes,
  SHA256 `aaa1a24d4ee45d34cfa258a7b870d21bda1e506256958cd907e38cb9cb7f3956`.
- The Stage100 timer code shifts the early boot BL at `0x8142e3e4` from
  `0x940012f0` to `0x940012f8`. Its new exact instruction was verified
  against the CI Mach-O and relocated payload; all 41 guard pins passed.
- Built `shim/out/cactus/cactus-trace-stage-100-boot.img`, 62,285,824 bytes,
  Android boot image v2, SHA256
  `e4ef99a70fab35bfa3e28d4422534b0718d49eabfa7eae605c9c553f06df289e`.
- Confirmed fastboot serial `3184a8a17d2b` and product `cactus`, then invoked
  the guarded 60-second COM25 watcher/fastboot flash runner.
  **The fastboot send failed**, reporting
  `FAILED (remote: 'low power, need battery charging.')`. The phone reported
  `battery-voltage: 3502mV`; `battery-level` was unsupported by this bootloader.
  The runner did not issue reboot, and no Stage100 boot image was flashed.

**Hardware outcome:** Stage100 is built and ready to retry after charging.
Its native handoff, timer recovery, Apple launchd main, and SpringBoard GUI
remain unverified on hardware. A previous successfully flashed Stage99
image is still the last verified boot configuration.

## November 10: repaired runtime guard and verified EL1 transition

The first successfully flashed Stage100 image returned to recovery because
the shim's separate runtime instruction table still pinned the Stage99
branch at physical address `0x8142e3e4` to `0x940012f0`. The Stage100
kernel instead contains `0x940012f8`. The early trace showed
`0x1952` then `0x20ff/0x19ff status=0x510`, proving that the
runtime `stage20b_arm()` rejected the old pin before EL1 transition.
The offline checker had been updated, but the runtime pinned table was not.

The shim now consumes `CACTUS96_WORD_8142E3E4` from the same header
generated from the SHA-verified kernel Mach-O and relocated payload.
The checker verifies that the runtime table uses this generated macro,
and retains the expected prior instruction for earlier stages.
Rebuilt the shim locally using the existing Stage100 CI kernel; all
41 native instruction guards passed. No XNU recompilation was required.

- Corrected boot image SHA256:
  `0ab9401518defa81c4d48ec75e300be3f2d403bc98fdb89be506d1e9ac413a4a`.
- Fastboot device `3184a8a17d2b` identified as `cactus` with
  battery voltage 3645mV. Boot partition flash and reboot both succeeded.
- COM25:
  `usb-captures/stage-cactus-20261110-002127-485/session-001-002139-320.bin`.
  115 valid frames, zero corruption, **11 missing sequence numbers**.
  Ordered handoff markers `0x2303`, kernel SHA prefix `0x2800`,
  `0x3500`, `0x3900` were received. Shim EL1 signal
  `0x20a1` also appeared, followed by the expected EL2 trap/return
  diagnostics including `0x20b3` and final status 0.

The strict Stage100 decoder reported NOT VERIFIED because of the 11
sequence gaps; this is **not** the same hard guard failure as the first
flash. The trace establishes a successful shim-to-EL1 transition
through the previous blocking point. Native XNU userspace and the
SpringBoard GUI still require framebuffer evidence.
