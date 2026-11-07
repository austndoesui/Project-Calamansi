# Cactus Stage40–42: native XNU early-C lookup checkpoints

Stage39 disabled the inherited MTK top-RGU watchdog successfully, but
COM25 stops transmitting while XNU owns the CPU, so silence after EL1
handoff does not identify the stalled instruction. These three builds
use **the identical CACTUS XNU Mach-O with patches 0086+0087** from
GitHub Actions run 40003701253, verified static instruction pins, and
the Stage39 watchdog fix. Each build replaces **one** original AArch64
instruction with a controlled BRK, while the separate Stage25 pmap
panic-site breakpoint remains armed. The shim's exception vector returns
to EL2 and flushes the register/TTBR/ESR trace through COM25.

| Build | Original VA | Original opcode | BRK | Hardware |
| --- | --- | --- | --- | --- |
| Stage40 | 0xfffffff007ac0c20 | 0x97fe7424 (BL) | #0xe40 | PASS, 165 valid frames, ESR 0xf2000e40 |
| Stage41 | 0xfffffff007a5dcb0 | 0xd10303ff (callee entry) | #0xe41 | PASS, 139 valid frames, ESR 0xf2000e41 |
| Stage42 | 0xfffffff007ac0c24 | 0x7100041f (CMP after BL) | #0xe42 | PASS, 123 valid frames, ESR 0xf2000e42, x0=1 |

The Stage40 and Stage41 captures establish that XNU executes the
boot-argument function call path and reaches the function's entry.
Stage42 confirms that first lookup **returns successfully** with x0=1.
The following b.ne to 0xfffffff007ac1194 is therefore not taken.
Stage43/45 target VA 0xfffffff007ac0c64 after the next lookup;
Stage44/46 target VA 0xfffffff007ac0c68 after its following call.

Captures are preserved outside Git:

- `../usb-captures/stage-cactus-20261024-111103-323/session-001-111156-240.bin`
- `../usb-captures/stage-cactus-20261024-112044-737/session-001-112131-534.bin`
- `../usb-captures/stage-cactus-20261024-112503-583/session-001-112601-430.bin`

All three captures: no missing/duplicate frames or CRC errors; verified
watchdog EN bit cleared before XNU handoff. The controlled exceptions
and vector restores succeeded. Full XNU boot and visible framebuffer
console remain outstanding.
