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
