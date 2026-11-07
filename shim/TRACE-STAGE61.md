# Stage61: validate GICv3 redistributor identity before enabling SGI8

Stage59 SGI1 and Stage60 SGI8 both reached native XNU framebuffer output,
but both reported `0x3ff00000040` after an attempted redistributor rearm.
In the snapshot encoding, bit `0x40` means the SGI-specific enable bit is
clear; `0x3ff` is the non-acknowledging highest pending Group1 interrupt
ID (spurious). The displayed `SGI8 sent` text confirms only a send attempt.
CPU0 interrupt readiness, BSD mount and PID1 have not been proven.

Stage61 retains the Stage60 SGI8 experiment and tests an earlier possible
error: an absent/zero-filled GICR frame can otherwise appear to have MPIDR
affinity 0 and be mistaken for the bootstrap CPU's redistributor. The
CACTUS-only patch checks architected GICR_PIDR2 architecture identity
(GICv3/v4) before accepting any GICR_TYPER affinity match, emits bounded
identity logs, reads back SGI8 and timer PPI enable, and keeps framebuffer
`ST61 SGI8 SENT, ENABLE=0/1` rather than overwriting the failed-enable
result with an unconditional send message. It does not bypass CPU readiness,
force IRQ state or change secure firmware.

Source patch `xnu/patches/0098-cactus-gicr-frame-validate-stage61.patch`;
source branch `stage61-cactus-gicr-id-guard`, commit `bf9dee9`.
GitHub Actions CACTUS DEVELOPMENT run `40225061014` **SUCCESS**.
Kernel `../stage61-kernel-run40225061014/kernel.development.cactus`:
17,158,328 bytes, SHA256
`15fdbdab0aa0cb1f9b7cccc9b78d23b3a1f14a016b709085c621d19d9d074775`.

Relocated 11-segment XNU payload
`shim/out/cactus/linux-chainload/stage61-relocated-payload.bin`:
16,574,048 bytes, SHA256
`3d9afc076f8a2b0dd1c612fac03b343703b107e2ecd0bf6bae21ca42c7ea66b9`.
Original entry physical address `0x8142d488`, C prologue `0x81ac327c`,
early-C join `0x81ac38ac`, post-checkpoint `0x81ac3908`, signed diagnostic
PID1 RAMDisk physical address `0x824bc000`, bootargs `0x824c8000`.
Strict XNU/ADT/RAMDisk guard **PASS**.

Stage61 Android boot-header-v2 image
`shim/out/cactus/cactus-trace-stage-61-boot.img`:
45,541,376 bytes, SHA256
`80a434938be775079c9cc48f6d02abd7f1d20ef18e612fa5bc0925a09a0a4d16`.
SHA256 matches `.sha256` sidecar. WSL shim suite: **50/50 tests PASS**,
including new Stage61 USB identity/tamper tests. `--require-stage61`
requires marker `0x6100`, reconstructed kernel SHA prefix
`0x15fdbdab0aa0cb1f`, and the precise XNU checkpoint opcode/PA.

The image has **not** been physically tested. At the final local check,
`fastboot devices -l` returned no device. With the authorized Redmi6A
serial `<REDACTED_DEVICE_SERIAL>` connected in fastboot, use the guarded runner:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1' -Stage 61 -CaptureSeconds 120
```

The next decisive physical evidence is the `ST61 bad GICR frame` or
`ST61 GICR match` log and final `ST61 SGI8 SENT, ENABLE=0/1` status.
If the matching, valid frame still ignores the enable write, inspect GICR
security group and access ownership; changing SGI IDs alone has already
failed. COM25 stops at native XNU handoff, so framebuffer output remains
the authoritative posthandoff evidence.
