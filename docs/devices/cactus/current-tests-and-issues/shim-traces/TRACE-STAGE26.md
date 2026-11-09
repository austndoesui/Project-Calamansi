# Stage 26 — early I/O table fix and old-kernel bridge experiment

**2026-10-23 hardware result: Stage31 flashed and traced successfully;
the old XNU framebuffer-height workaround did not bypass the panic.**
The permanent source patch is applied locally but still needs a new XNU
kernel build. Full startup and visible framebuffer output remain unproven.

## Stage31 hardware run

The authorized Redmi 6A (`fastboot getvar product: cactus`) accepted
`fastboot flash boot` and `fastboot reboot`, both reporting `OKAY`.
The raw USB watcher captured four COM25 sessions in
`F:\ROM\patching\redmi 6a xnu\usb-captures\stage-cactus-20261023-224829-332`.

Session `session-002-224943-912.bin`: **72 complete CRC-valid frames,
zero corruption, gaps, duplicates or regressions**. Strict decoding
with `--require-stage26` returned
`STAGE26 GENUINE XNU FAULT CAPTURED; COM25 HELD`.

The new video-geometry evidence confirms `0x2600` (1440 → 640 rows,
2880-byte stride) and `0x2601` before handoff. XNU entered native EL1
(`0x20a1`) and then faulted at **`0xfffffff0072a9e64`**, ESR_EL1
**`0x02000000`**, the same `_DebuggerTrapWithState` undefined opcode
seen during Stage24. Registers still identify the
`_pmap_map_bd.cold.1` panic path. The fault was logged and the
shim restored its exception vectors and retained COM25 diagnostics.

This means the reduced-height workaround **did not demonstrate progress
beyond the old pmap failure**. Other early I/O mappings or VA
reservation may continue beyond the missing L1 region. Only testing
the rebuilt kernel carrying the actual source fix can establish whether
correct parent-table allocation resolves the panic.

Session 001 and 004 each contained only 44 preflight frames (2,464
bytes). They are not full XNU outcomes. The raw capture directory also
contains session 003; do not count separate reconnects as independent
successful kernel boots.

The post-run fastboot check returned no device; the USB watcher has
ended. Enter fastboot manually and use
`fastboot oem reboot-recovery` to return to TWRP when needed.

## Hardware-measured failure (Stage25)

The first native XNU panic in `pmap_map_bd()` occurs while mapping the
framebuffer physical interval `0x5e605000..0x5e9fa000` (exclusive).
The initial virtual address was `0xfffffff049dbb000`. When the mapping
reached `0xfffffff04a000000`, the L1 descriptor at physical
`0x824c1e08` (TTBR1 `0x824c1000`) was zero. Stage25 captured this with
77 CRC-valid COM25 frames and no sequence gaps. See `TRACE-STAGE25.md`.

## Permanent source fix, pending XNU rebuild

The new ordered XNU patch
`xnu/patches/0086-cactus-early-io-l1-tables.patch` inserts a
Cactus-only `init_ptpages()` call in `osfmk/arm64/arm_vm_init.c`
immediately after the early I/O VA extent calculation, and before the
loop allocating L3 tables. It aligns the start down to the 1 GiB L1
boundary and allocates missing L2 parent tables with XNU's actual
page-table allocator:

```c
init_ptpages(cpu_tte, va_l1 & ~ARM_TT_L1_OFFMASK, va_l1_end,
    FALSE, ARM_DYNAMIC_TABLE_XN | ARM_TTE_TABLE_AP(ARM_TTE_TABLE_AP_USER_NA));
```

`git apply --check` passed against the local source at
`/home/lapdq/xnu-cactus`, and the patch was applied there successfully;
`git diff --check` passed. **The source fix is not in the embedded
Stage31 Mach-O kernel.** That kernel still needs a complete XNU build
with the new patch before we can claim the real page-table repair is
running on-device. The local WSL environment lacks the macOS/Xcode
build stack, and the GitHub CLI reported an invalid authentication token.

## Stage31: temporary diagnostic bridge using the old Mach-O

The user requested maximum boot progress while the rebuilt kernel is
unavailable. Build stage `31` therefore retains the hardware-proven
Stage23/24 native XNU entry and synchronous fault logger but **does not**
install Stage25's deliberate `BRK #0xe25` at the pmap panic call.

Stage31 verifies the original 720 x 1440, 2880-byte-stride 32-bit video
geometry, runs the bounded pixel RAM marker test, and waits through the
preflight USB enumeration window. Immediately before the native XNU
handoff, it temporarily changes only `boot_args.Video.v_height` from
`1440` to `640`, cache-cleans that value and emits:

- `0x2600` — original height `1440`, restricted height `640`, row stride `2880`.
- `0x2601` — framebuffer PA `0x5e605000`, previous mapping start VA
  `0xfffffff049dbb000`, and known failing L1 boundary
  `0xfffffff04a000000` (the latter two are historical measurements,
  not observations from the new boot).
- `0x26ee` — a geometry invariant failed; XNU is not entered.

The 640-row mapping size is `0x1c2000` bytes. Stage25 measured only
`0x245000` bytes between the mapping's initial VA and the invalid L1
boundary. The reduced size therefore fits within that interval even
with 16 KiB rounding, **if the old kernel places the next mapping at
the same VA**. This hypothesis requires a device test; it is not a
general framebuffer or page-table fix. A changed framebuffer height
also means full panel contents and on-screen XNU logging cannot be
assumed to work.

The stage keeps original XNU register snapshots (`0x2400..0x2407`),
MMU/exception context, vector restoration, and COM25 hold on the first
fault. The strict decoder requires `--require-stage26` and distinguishes
a complete first-fault report from an EL1 entry with an unknown outcome.

## Local build and test evidence

WSL `shim/build_trace_probe.sh 31` completed successfully, including
`check_stage22_entry.py`, Android boot-v2 and DTB structure verification.

- Image: `shim/out/cactus/cactus-trace-stage-31-boot.img`
- Size: **45,506,560 bytes**
- SHA256: `0ccad55a727f7838fbe93d06ce7729b08d07de6cc3b4927ddc363e37195e0b06`
- Six targeted Stage22–26 decoder and payload tests: **PASS**.
- `git diff --check` and Python compilation: **PASS**.

Run USB capture *before* reboot, once hardware testing is possible:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\shim\watch-cactus-usb.ps1 -Seconds 180
```

After confirming `fastboot getvar product` is `cactus`, flash the
Stage31 image using the existing authorized fastboot workflow, then
decode the resulting raw capture:

```powershell
python shim/decode-cactus-usb.py 'path/to/session.bin' --require-stage26 --show 110
```

**Historical pre-test note:** before this hardware run, an earlier
fastboot check was blocked by tool safety review. The subsequent
explicitly authorized flash and reboot completed successfully.

## Next steps

If Stage31 reaches native XNU and captures a new fault, identify the
first failing subsystem and retain the raw binary capture. If it
hangs with only handoff markers, investigate MMU/exception coverage and
whether a different early `io_map()` allocation still crosses an
unallocated L1 region. Rebuild the real XNU image with patch 0086 when
the macOS toolchain is available, then use the same logger to verify
the original framebuffer mapping passes without reducing its height.
LK's actual display scanout address still needs confirmation before a
visible text console can be claimed.
