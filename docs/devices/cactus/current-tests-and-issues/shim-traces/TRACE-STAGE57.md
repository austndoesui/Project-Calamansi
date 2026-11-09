# Stage57: boot CPU0 readiness and SGI recovery

**2026-10-25: Built, verified offline; hardware Stage57 test pending.**
Stage56 was flashed to the Redmi 6A, and the last native framebuffer line was
`ST56 CPU processor_start done`. This shows that `processor_start()` returned,
while completion of the `cpu->initialized` and `SIGPdisabled`/SGI readiness checks
remained unproven. The Stage56 prehandoff COM25 USB capture had 81 clean frames.

This Stage57 patch preserves the existing native XNU, LK framebuffer and diagnostic
RAM disk. Source inspection confirmed Cactus MT6765 **GICv3**, with `ICC_SGI1R_EL1`
and Group 1 `sleh_irq`; do not convert it to GICv2. New additive patch
`xnu/patches/0094-cactus-cpu0-sgi-stage57.patch` adds native framebuffer markers
around boot CPU `initCPU()`, counts SGI1 IRQ deliveries in `sleh_irq`, and reports
initialization vs SIGPdisabled vs IRQ delivery separately. If CPU0 initializes but
the signal readiness remains blocked, `SweetCPU::startAll()` retries its self-SGI
up to three times, 250 ms apart. It never artificially clears `SIGPdisabled` or
marks an uninitialized CPU ready. The 5-second bounded startup timeout remains.
The Stage55 KPERF/BSD gates are still active if CPU publication completes.

Source: clean branch `stage57-cactus-cpu0-irq-recovery`, commit `d1a69f6`;
CACTUS DEVELOPMENT XNU GitHub Actions run **40167462565 SUCCESS**.
Downloaded `../stage57-kernel-run40167462565/kernel.development.cactus` SHA256
`7a0b778d113b3a66da2bc4d64c98f4ba2fef81c7ac6403f01a481ced3b396cd5`.
Kernel entry remains PA `0x8142d488`. Stage57's audited early C entry is
`0x81ac2d3c`, continuation `0x81ac336c` (word `0xb0ffaca1`), and checkpoint
`0x81ac33c8` (word `0xb0ffb5a8`). Native MMU pins and exceptions verified.

Stage57 unrelocated payload: `shim/out/cactus/payload-stage57.bin`; relocated
`shim/out/cactus/linux-chainload/stage57-relocated-payload.bin` SHA256
`e2970174ed89542d4752a037f849526f7fc11d968130f2ccf8c9bded213c804f`.
The signed diagnostic init Mach-O is unchanged, SHA256
`d187f6f1529b9290dfcd64d6923ce2a59e30f6d9fdb463970728744d806e9991`;
11 payload segments and `rd=md0` remain, RAMDisk PA `0x824bc000`, boot_args
PA `0x824c8000` and framebuffer PA `0x7f4db000`. Exact XNU/ADT/RAMDisk guard PASS.

**Stage57 boot image:** `shim/out/cactus/cactus-trace-stage-57-boot.img`, 45,541,376
bytes, Android boot image v2, SHA256
`f3538425d08b11a1fe83f3d0bb63d35060deb5d0b1ce78298083fcdcb478ee29`.
Built by `bash shim/build_trace_probe.sh 57`; 46/46 WSL shim tests PASS.
USB prehandoff marker `0x5700` and `0x2800` pin Stage57 kernel SHA prefix
`0x7a0b778d113b3a66`. Host decoder: `--require-stage57`.

Last host `fastboot devices -l` returned no device; **no Stage57 flash or native
runtime result was obtained**. For an authorized hardware trial with verified
serial `<REDACTED_DEVICE_SERIAL>`, product `cactus`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1' -Stage 57 -CaptureSeconds 120
```

Native framebuffer last `ST57` (and any later `ST56`/`ST55` BSD status) will
distinguish CPU0 initialization, IRQ readiness, SGI delivery and CPU publication.
Only the physical framebuffer and subsequent native logs can prove BSD or PID1.
