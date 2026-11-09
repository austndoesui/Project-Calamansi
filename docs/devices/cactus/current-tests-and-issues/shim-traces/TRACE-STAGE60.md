# Stage60: SGI8 trial and GICv3 security/redistributor diagnosis

Stage59 on hardware reached `ST59 SGI1 sent`, followed by
`ST59 GIC SGI after rearm status=0x3ff00000040`. The low bit `0x40`
means the GICR SGI1 enable bit was clear after the re-arm write.
`0x3ff` is an empty Group-1 highest pending INTID. Kernel launch and
USB prehandoff were successful; actual SGI delivery, BSD mount and PID1
are still unproven.

Stage60 source patch `xnu/patches/0097-cactus-sgi8-gic-diag-stage60.patch`
changes the CACTUS-only build to SGI8 throughout the existing XNU
sender, redistributor enable and interrupt handler using the shared
`SWEET_IPI_SGI` constant. Linux MT6765 kernel describes GICD at
`0x0c000000`, GICR at `0x0c100000`, and uses Group1NS SGIs. Switching
to SGI8 is a *hypothesis test* for a firmware-reserved SGI1, not a
proven solution or an instruction to bypass CPU readiness.

The patch also logs MPIDR, selected redistributor base and TYPER,
GICR_CTLR/WAKER, IGROUPR0, IGRPMODR0, NSACR, SGI enable/pending,
and bounded GICR_CTLR.RWP completion after the enable write.
It does not modify firmware security groups, bypass SIGPdisabled,
or force CPU readiness. Distinct Stage60 screen statuses remain visible
if SGI8 cannot be enabled. The signed Stage55 Mach-O diagnostic
PID1 root stays in the image for the eventual BSD test.

Source commit: `558f360`, branch `stage60-cactus-sgi8-gicr`;
CACTUS DEVELOPMENT Actions run `40177248576` **success**.

Build provenance and strictly audited handoff:

- Kernel: `../stage60-kernel-run40177248576/kernel.development.cactus`,
  17,158,344 bytes, SHA256
  `2f3b02c004763c7a4bed2c9ecd58d0c789e9d5399566a862006252858c186507`.
- 11-segment relocated payload:
  `shim/out/cactus/linux-chainload/stage60-relocated-payload.bin`,
  16,574,064 bytes, SHA256
  `f68d4a5a9519328e64873bb7adc697e638c6ae97c0c700709438ca64c784b633`.
- Native entry PA `0x8142d488`, C prologue PA `0x81ac326c`, continuation
  PA `0x81ac389c` (opcode `0xb0ffaca1`), post-checkpoint PA
  `0x81ac38f8` (opcode `0xb0ffb5a8`). Native TTBR0 helper and signed
  Mach-O PID1 are independently verified; RAMDisk PA `0x824bc000`,
  bootargs PA `0x824c8000`.
- Android boot-image-v2:
  `shim/out/cactus/cactus-trace-stage-60-boot.img`, 45,541,376 bytes,
  SHA256 `4f06ddb697807be4b7138d9552cf7723129242d81cd42ce14eec56a81cd9f1b0`.
- `python3 -m unittest discover -s shim -p 'test_*.py'` from WSL:
  **49 passed**. Exact relocated XNU/ADT/RAMDisk guard: **PASS**. Host
  `shim/decode-cactus-usb.py --require-stage60` pins new `0x6000` and
  `0x2800` identity events to kernel SHA prefix `0x2f3b02c004763c7a`.

When the device is in fastboot, the guarded command is
`powershell -NoProfile -ExecutionPolicy Bypass -File
'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1'
-Stage 60 -CaptureSeconds 120`. It checks device serial `<REDACTED_DEVICE_SERIAL>`,
product `cactus` and the SHA sidecar before flashing. No Stage60 flash
occurred in this build session because fastboot listed no device.

Next hardware evidence: the final `ST60` framebuffer status and new
GICR register readback lines. A successful COM25 preflight verifies
the shim through handoff only.
