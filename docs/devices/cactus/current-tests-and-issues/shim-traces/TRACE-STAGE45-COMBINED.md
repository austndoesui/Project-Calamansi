# Stage45–47 — combined XNU startup + Cactus scanout reconnaissance

These images pack several independent checks into **each** hardware boot:

1. Same rebuilt 0086+0087 CACTUS XNU payload, full 720x1440 boot args,
   guarded native EL1 startup BRK and original Stage25 pmap sentinel.
2. Stage39 top-RGU watchdog disarm and proven COM25 binary trace path.
3. Read-only MT6765 OVL0/RDMA0 register snapshot with physical device
   bases and offsets taken from the WSL MT6765 4.19 kernel sources.
4. A bounded, already-tested Stage23 RGB marker only if the OVL0 layer
   is **enabled** and reports the exact known buffer 0x5e605000 and
   2880-byte pitch. No speculative register writes or foreign RAM writes.

The display base addresses come from
`arch/arm64/boot/dts/mediatek/mt6765.dts`:
OVL0=0x1400b000 (0x1000 aperture) and RDMA0=0x1400d000.
Offsets from
`drivers/misc/mediatek/video/mt6765/dispsys/ddp_reg_ovl.h`
and `ddp_reg_dma.h`:

| COM25 event | Registers / meaning |
| --- | --- |
| 0x4500 | OVL base, EN (0x00c), SRC_CON (0x02c) |
| 0x4501 | OVL STA (0x000), ROI_SIZE (0x020), L0_CON (0x030) |
| 0x4502 | OVL L0_ADDR (0xf40), PITCH (0x044), SRC_SIZE (0x038) |
| 0x4503 | OVL L1/L2/L3 memory addresses (0xf60/0xf80/0xfa0) |
| 0x4504 | RDMA base, GLOBAL_CON (0x010), MEM_CON (0x024) |
| 0x4505 | RDMA MEM_START_ADDR (0xf00), pitch (0x02c), size |
| 0x4506 | Candidate: upper a=OVL L0 enabled, low a=buffer/stride match; b=OVL addr; c=known buffer |
| 0x4507 | Conditional test-bar RAM readback; zero if source not matched |

If layer address differs from the boot_args buffer, that is a useful
explanation for why earlier RAM writes did not change the MI logo.
An OVL address can be an IOVA, so even an exact match remains a *candidate*.
Actual visible scanout requires a human-observed display change and
controller-path validation, neither of which is proven by readback.

The simultaneous XNU diagnostic is selected by image:

| Combined build | Native BRK | VA | What it checks |
| --- | --- | --- | --- |
| Stage45 | #0xe43 | 0xfffffff007ac0c64 | Reaches call after second early-C lookup |
| Stage46 | #0xe44 | 0xfffffff007ac0c68 | Returns from the next init call |

The checked BRK intentionally halts the run and returns exception state
to EL2. **They cannot both fire in a single boot** with the current
one-shot exception logger. Start with Stage45; only test Stage46 if
Stage45 confirms its checkpoint. No XNU operating-system boot or live
framebuffer text console is claimed by these builds.

Both locally built 2026-10-24; Android boot-v2 verified:

- Stage45: `shim/out/cactus/cactus-trace-stage-45-boot.img`
  SHA256 `8441aa12a94cd29096af823fc63f150df11d417f6e2933bacf087039f2c7e23f`
- Stage46: `shim/out/cactus/cactus-trace-stage-46-boot.img`
  SHA256 `8a29339efac20d3c9fcb9fe119ddee6925509e98be077ae3f0c69bf313f9327e`

## Stage45 actual hardware result — PASS (2026-10-24)

Fastboot product `cactus`, flashed and rebooted with Stage45.
Raw COM25 capture:
`../usb-captures/stage-cactus-20261024-124411-507/session-001-124510-747.bin`,
**8792 bytes / 157 valid frames**, zero CRC errors, gaps, duplicates,
regressions or unmatched bytes.

- `0x4500`: OVL0 EN=`0x1`, SRC_CON=`0x3` (L0 and L1 enabled).
- `0x4501`: OVL status=`0x19`, ROI=`0x05a002d0` (720x1440),
  L0_CON=`0x21ff`.
- `0x4502`: L0 address=`0x7f0d0000`, pitch=`0xb80` (**2944**),
  L0 size=`0x05a002d0` (720x1440).
- `0x4503`: L1 address=`0x7f4db000`; L2/L3 addresses zero. L1
  begins exactly `0x40b000 = 2944*1440` bytes after L0.
- `0x4504`/`0x4505`: RDMA0 GLOBAL_CON=`0x101`, MEM_CON=`0`,
  MEM_START_ADDR=`0`, MEM_SRC_PITCH=`0`, output 720x1440.
  RDMA0 is receiving an upstream OVL stream.
- `0x4506`: enabled L0, **mismatch** to boot_args framebuffer
  `0x5e605000`/pitch 2880; `0x4507` all zero = no framebuffer
  writes attempted.
- `0x3900`: top-RGU MODE `0x5d -> 0x5c` (watchdog EN disabled).
- `0x20a1`: native XNU entered EL1.
- `0x2206`: ESR_EL1=`0xf2000e43`, ELR_EL1=
  `0xfffffff007ac0c64`; **next native init call reached**.
- `0x220b`: (1,1,1) original instruction and vectors restored.

The two actual OVL0 layer addresses offer a concrete explanation for
why writes to the *different* `0x5e605000` boot_args buffer were not
visible. They are register source addresses, possibly device IOVAs.
The next combined test must capture L1 pitch, format/alpha and offsets
and classify the source ranges against the boot FDT before a pixel write.

**Stage46 remains offline-built, hardware pending.** Before a new
hardware test, confirm fastboot product `cactus` and start
`shim/watch-cactus-usb.ps1` independently. The user's boot/recovery
rollback images are already available.

## Stage47 — next combined build (hardware pending)

Stage47 combines the Stage46 native XNU return breakpoint
`0xfffffff007ac0c68` / `BRK #0xe44` with Stage45's validated register
observations. It additionally performs these **read-only** checks:

| COM25 event | Fields |
| --- | --- |
| `0x4700` | OVL L1_CON, L1_SRC_SIZE, L1_OFFSET |
| `0x4701` | OVL L1_ADDR, L1_PITCH, L0_ADDR |
| `0x4702` | L0_OFFSET, L0_CLIP, L1_CLIP |
| `0x4703` | L0 pitch × source height, L1–L0 address separation, L1 enabled/contiguous flags |
| `0x4705` | FDT memory/reserved range counts, computed L0/L1 surface spans |
| `0x4704` | FDT status flags, L0 and L1 hardware-source addresses |
| `0x4706` | Boot-argument framebuffer address, pitch, dimensions |

FDT status `0x4704.a` flags: bit0 parsed; bit1/bit2 candidate L0/L1
spans lie within some memory bank; bit3/bit4 the regions are also
outside all FDT reserved ranges. Neither result proves address
translation identity: OVL addresses can be IOVAs. Do not write those
locations without verifying the IOMMU mapping and active visible
layer/pixel format.

Boot image:
`shim/out/cactus/cactus-trace-stage-47-boot.img`,
45,508,608 bytes; SHA256
`3ccea4c45baac845deb082b80e6c00aeb9b71104fb9123849aa1b8f58423c08a`.
Built locally in WSL with Stage44 strict instruction guard and Android
boot-v2 validation; 8 regression tests passed.

Strict trace verification after hardware capture:

```powershell
python shim/decode-cactus-usb.py 'PATH_TO_RAW_SESSION.bin' --require-combined-stage 47 --show 100
```

The new strict `--require-combined-stage 45` check was verified on the
real 157-frame Stage45 capture. Stage47 was subsequently flashed and
hardware-tested; see the result below.

## Stage47 actual hardware result — PASS (2026-10-24)

Fastboot serial `<REDACTED_DEVICE_SERIAL>` and product `cactus` confirmed.
Flashed checked Stage47 boot image and rebooted. Standalone COM25
watcher produced raw file
`../usb-captures/stage-cactus-20261024-140303-742/session-001-140400-979.bin`.
**212 valid frames, 11,872 bytes**, zero CRC errors, gaps,
duplicates or sequence regressions. Strict
`--require-combined-stage 47` decoder **PASS**.

Native XNU entry `0x20a1` and intentional `BRK #0xe44`:
`0x2206 ESR_EL1=0xf2000e44`, ELR_EL1
`0xfffffff007ac0c68`. `0x220b=(1,1,1)` confirms original
instruction and exception vector restoration. This verifies that
the next early-C init call returned; the intentional BRK prevents
normal continuation, so an OS boot is still unverified.

OVL0 `SRC_CON=3` enables both layers. L0 source
`0x7f0d0000`, pitch **2944**, size **720x1440**. L1 source
`0x7f4db000`, pitch **2880**, size **720x1440**, L1_CON
`0x21ff`, offset `0`. Layer-source separation is exactly
`0x40b000 = 2944*1440` bytes. RDMA0 is in direct-link mode
(`GLOBAL_CON=0x101`, memory source addr/pitch `0`).
FDT parsed one memory bank and 17 reserved ranges. Classification
`0x4704.a=7` indicates both hardware source spans fall inside a
RAM bank but neither passes the unreserved-range test.

The boot args instead identify framebuffer source
`0x5e605000` with 2880-byte stride. Do not assume OVL source
registers are writable CPU physical addresses; first resolve
the LK/OVL/M4U mapping and reserved-memory carveout. No display
memory was written in Stage47, and on-screen output remains
unverified.
