# Stage62: physical GICv3 redistributor census before XNU

## Evidence and objective

Stage61 reached the native framebuffer but panicked in `find_gicr_pe_base()`
(`pe_fiq.c:99`), before its detailed framebuffer logs: no redistributor
frame passed both the `GICR_PIDR2` revision and `GICR_TYPER` affinity tests.
Earlier Stage59 SGI1 and Stage60 SGI8 both showed `0x3ff00000040`
(redistributor SGI-enable readback clear, Group1 HPPIR1 spurious). The
`cactus-xnu-stage52` panic header is a reused framebuffer title.

Linux MT6765 DTS confirms GICD physical `0x0c000000` (size `0x40000`)
and GICR physical `0x0c100000` (size `0x200000`); the generated Apple
device-tree uses /arm-io ranges starting at `0x01000000` and encodes GICR
relative offset `0x0b100000`. The source of XNU's runtime mapped-address
readback is still unconfirmed. PIDR2 `0xffe8`, TYPER `0x8`, redistributor
stride `0x20000` are architected GICv3 offsets.

## Stage62 experiment

The working Stage61 XNU Mach-O, ADT, bootargs and signed diagnostic PID1
RAMDisk remain **byte-for-byte unchanged**. The MMU-off EL2 USB shim adds
a **read-only**, bounded physical MMIO snapshot immediately after COM25
initialization, before entering XNU. It neither writes GIC registers nor
modifies firmware, LK, storage layout or CPU-ready state.

USB event `0x6200` encodes `(MPIDR_EL1, GICD_PIDR2<<32|GICD_TYPER,
GICR physical base)`. Event `0x6201` repeats for each 0x20000-byte
redistributor frame up to the first GICR_TYPER.Last or 16 frames, encoding
`(physical address, GICR_PIDR2, GICR_TYPER)`. Event `0x6202` records
`(SOC_BASE, ADT relative GICR offset, expected GICR physical address)`.
This provides independent register evidence when Stage61 XNU panics.

**Critical limitation:** this is a diagnostic. Stage61's native panic is
still expected if the original identity and affinity check cannot find a
frame. The COM25 capture can tell whether the same registers were
readable before XNU changed the MMU mappings; it cannot yet prove IRQ
delivery or native BSD/PID1 startup.

## Offline verification and image

- Embedded original Stage61 relocated payload:
  SHA256 `3d9afc076f8a2b0dd1c612fac03b343703b107e2ecd0bf6bae21ca42c7ea66b9`.
- `shim/check_stage61_xnu.py` XNU/ADT/RAMDisk guard: **PASS**.
- WSL `python3 -m unittest discover -s shim -p 'test_*.py'`: **51 PASS**.
- Android boot image v2:
  `shim/out/cactus/cactus-trace-stage-62-boot.img`, 45,541,376 bytes;
  SHA256 `f7c27939c9ff8a41d386034a746b75f680757f9189a990539761d8c44ac1354d`.
  `.sha256` matches independently computed file SHA256.

The authorized guarded flash/capture command, **once the cactus phone is
actually connected in fastboot** (serial `<REDACTED_DEVICE_SERIAL>`), is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1' -Stage 62 -CaptureSeconds 120
```

`shim/decode-cactus-usb.py` automatically prints a `STAGE62_GICR` line
for every recorded frame; `--require-stage62` adds the strict complete
frame/ordering/kernel-identity validation. A dropped CLOG frame may fail
strict completeness despite correct surviving observations. Inspect the
raw `STAGE62_GICR physical=... pidr2=... typer=... affinity=...` values
before changing XNU's mapping or security configuration.

The Stage62 image has **not** been flashed yet: the last `fastboot devices -l`
returned no attached device. Existing device rollback images are already
available; do not regenerate backups.
