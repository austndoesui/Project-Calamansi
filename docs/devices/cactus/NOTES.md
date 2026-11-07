# Cactus XNU working notes

**November 3, 2026 hardware update:** Stage62 was flashed successfully on Redmi 6A `<REDACTED_DEVICE_SERIAL>`. COM25 captured 204 valid frames, no corrupt frames, 12 missing sequences; strict capture validation was INCOMPLETE due to gaps. All eight physical redistributor records survived (`PIDR2=0x3b`), CPU0 frame `0x0c100000` had `TYPER=0`, and MPIDR was `0x80000000`. Capture: `../usb-captures/stage-cactus-20261103-002545-681`. The Stage61 native-XNU mapping/select failure remains unresolved. The next consolidated build requirements are in [Stage63 plan](docs/STAGE63-CONSOLIDATED-BRINGUP.md); no Stage63 image has been built yet.

**Stage63 kernel build:** CACTUS DEVELOPMENT GitHub run `41507227468`
completed successfully from patch `0099`/commit `8e09cda`. Downloaded kernel
and repacked/relocated source payload are available locally. The Stage61
early-C instruction guard detects changed code, so a validated Stage63
boot image has not been packaged or flashed; new branch pins are required.

**Updated:** 2026-10-26. Device: Xiaomi Redmi 6A (`cactus`, MT6761/MT6765). Current working branch: `stage28-cactus-io-extent`. The firmware and boot images are experimental; **XNU has not booted an OS**.

**CURRENT: Stage62 GICR physical census boot image BUILT, hardware trial pending.**
Stage61 physically flashed and panicked in `find_gicr_pe_base()` at
`pe_fiq.c:99`, before the full-screen native console. It rejected all
redistributor frames by identity/affinity; this does not prove why the
registers were unreadable or mismatched. Stage62 samples actual MMU-off
physical GICD/GICR identity, affinity and ADT-relative address over COM25
without changing the signed Stage61 XNU payload. Built Android v2 boot
image `shim/out/cactus/cactus-trace-stage-62-boot.img` (45,541,376 bytes),
SHA256 `f7c27939c9ff8a41d386034a746b75f680757f9189a990539761d8c44ac1354d`,
strict XNU/ADT/RAMDisk guard PASS, **51/51** WSL shim tests PASS. No Stage62
hardware test yet; see `shim/TRACE-STAGE62.md`.

**PRIOR: Stage61 GICR identity-guard image built and physically tested.**
Stage61 source commit `bf9dee9` on `stage61-cactus-gicr-id-guard` and
GitHub Actions `40225061014` **SUCCESS**. Kernel Mach-O SHA256
`15fdbdab0aa0cb1f9b7cccc9b78d23b3a1f14a016b709085c621d19d9d074775`;
45,541,376-byte `shim/out/cactus/cactus-trace-stage-61-boot.img` SHA256
`80a434938be775079c9cc48f6d02abd7f1d20ef18e612fa5bc0925a09a0a4d16`.
Strict relocated XNU/ADT/RAMDisk guard PASS, 50/50 WSL shim tests PASS.
Stage61 validates GICR_PIDR2 before accepting bootstrap-CPU affinity,
preserves on-frame SGI8 enable readback and logs SGI8/PPI27 status.
**No Stage61 device test yet:** fastboot device was not detected during
final build checks. See `shim/TRACE-STAGE61.md` for image/provenance and
guarded hardware test command. No BSD root or PID1 execution proven.

**PRIOR: Stage60 SGI8 / redistributor readback flashed.** Stage59
boot flashed successfully, COM25 captured 81 valid Stage59 frames, and the
native framebuffer reached `ST59 SGI1 sent` with
`ST59 GIC SGI after rearm status=0x3ff00000040`. SGI1's GICR_ISENABLER0
enable bit remains clear even after rearming; the CPU sees spurious Group1
highest pending INTID `0x3ff`, so CPU0 readiness does not complete. Stage60
tries the consistent Group1NS SGI8 constant (sender, enable, handler), logs
the redistributor identity and security-group registers, and performs bounded
GICR RWP wait. Kernel build Actions `40177248576` **success**, source commit
`558f360`, and source Mach-O SHA256
`2f3b02c004763c7a4bed2c9ecd58d0c789e9d5399566a862006252858c186507`.
Stage60 boot image `shim/out/cactus/cactus-trace-stage-60-boot.img` is
45,541,376 bytes, SHA256
`4f06ddb697807be4b7138d9552cf7723129242d81cd42ce14eec56a81cd9f1b0`.
The strict relocated XNU/ADT/RAMDisk guard, source boot image checksum,
and 49/49 WSL tests passed. Stage60 was physically flashed; COM25 captured
80 valid frames with one missing sequence, and the native display reported
`ST60 SGI8 sent` with `ST60 GIC SGI8 rearm status=0x3ff00000040`.
Thus SGI8's redistributor enable was also clear, and no pending Group1
interrupt was observed. No BSD root mount/PID1 execution proven.
See `shim/TRACE-STAGE60.md`.

**PRIOR: Stage56 CPU synchronization diagnostic FLASHED; processor_start returned.**
Stage55 was successfully flashed and the phone's native screen stopped at
`ST55 KPERF early enter`. The Stage56 XNU source patch adds markers around
`ml_wait_max_cpus()`, `ml_set_max_cpus()` and `SweetCPU::startAll()` to identify
the actual CPU initialization wait. CACTUS XNU Actions run `40128807392`
succeeded after correcting C++ linkage. The distinct boot image
`shim/out/cactus/cactus-trace-stage-56-boot.img` (45,541,376 bytes) SHA256
`c34f8a48e5d4aaf2193c2d08f14bbdc057e85d6b4fd5c80d4bda463e78589a6c`
passes the exact native XNU/ADT/RAMDisk guard and **45/45** WSL shim tests.
Stage56 was physically flashed and its native framebuffer reached
`ST56 CPU processor_start done`; BSD/PID1 remain unconfirmed.
See `shim/TRACE-STAGE56.md` for exact code pins, source commit and test command.

**PRIOR: Stage55 BSD-GATE + STATIC DIAGNOSTIC PID1 IMAGE FLASHED; KPERF ENTRY REACHED.**
Stage54's physical framebuffer now proves `ST54 vm_set_restrictions done`, after
IOKit lockdown and matching completed. The Stage55 kernel compiled on Actions
run `40123102056`, and the separately built Android boot image is
`shim/out/cactus/cactus-trace-stage-55-boot.img` (45,541,376 bytes), SHA256
`79831361a4f342bc7ae6f7f43a5e1fd6a96b50153970e9ad36d56de254ce086c`.
Stage55 adds markers before/after KPERF and BSD gates, plus a signed static
diagnostic PID1 as an 11th in-memory root segment, via `rd=md0`. The relocated
ADT RAMDisk pointer bug has been corrected, and all **44** shim tests and
native-image guards pass in Ubuntu WSL. Stage55 was flashed successfully and
reached `ST55 KPERF early enter`. See `shim/TRACE-STAGE55.md`. Neither BSD
entry nor PID1 nor original iOS16 dyld/launchd are device-proven.

**PRIOR: Stage54 IOKit/BSD DEBUG IMAGE BUILT; STAGE54 SCREEN PROGRESS CONFIRMED.**
Stage54 XNU Actions run `40118509429` succeeded, and the exact new kernel
was integrated into `shim/out/cactus/cactus-trace-stage-54-boot.img`.
Image SHA256 `c1c5fe8c342ab2049e0d4daa47b483f6754498eb6b3b36fb18ce6af235e446f6`.
Static machine-code/ADT verification, boot-image validation and **43**
shim unit tests passed. New framebuffer progress checks surround IOKit
lockdown/matching, CPU VM restrictions and BSD entry. No fastboot device
was connected when checked, so the Stage54 image has **not** been flashed.
See `shim/TRACE-STAGE54.md` for exact binary provenance and hardware gate.

**PRIOR: Stage53 SMALL-FONT XNU IMAGE FLASHED / NATIVE DISPLAY PROVEN.**
Stage51 showed native XNU console output on the actual phone; Stage52
reached native Mach IPC logging after a verified 79-frame COM25 handoff.
Stage53 fixes the oversized framebuffer text with 8x16 glyphs (90x90
characters), reserves seven banner/status rows, enables verbose XNU
startup and adds further Mach/BSD progress marks. Kernel CI run
`40111491409` succeeded; the Stage53 Android boot image is
`shim/out/cactus/cactus-trace-stage-53-boot.img`, SHA256
`a6601e7f5264139c21c71bd9513e3175a6d3876a46f1ff0e53a498432607990c`.
**42 shim tests and all static gates PASS; the image was flashed on
2026-10-24.** A COM25 trace captured 78 valid frames and one sequence
gap. The owner's physical 81-line `../xnufboutput.txt` shows the
Cactarwin header and real XNU through VM, Mach IPC, and IOKit
platform initialization. Its last header status `PE_lockdown_lockit`
corresponds to source marker `PE_lockdown_iokit` before the call.
Stage54 should instrument its `zalloc_iokit_lockdown()` and
`StartIOKitMatching()` calls and the subsequent BSD entry boundary.
The first memory root and static PID 1 can be prepared in parallel.
See `shim/TRACE-STAGE53.md`, `shim/TRACE-STAGE54-PLAN.md` and
`docs/CACTUS-USERLAND-PLAN.md`. The iPhone X iOS 16.7.16 (20H392)
IPSW is required only for later original-Apple dyld testing.

## Stage 28 hardware result and next source fix

- **2026-10-24 Stage50 BUILT (hardware trial pending):** Boot image
  `shim/out/cactus/cactus-trace-stage-50-boot.img`, 45,508,608 bytes,
  SHA256 `3db03add61280050e03d83c9c84c1803799e06db8428915dfda25798c04f43b0`.
  After the Stage49 physical-display and readback guards, redirects
  XNU boot_args Video from the inactive buffer `0x5e605000` to the
  live LK OVL0 layer1 `0x7f4db000`. Full native XNU entry remains
  enabled. The display console and full OS boot remain unverified.
- **2026-10-24 Stage49 HARDWARE PREFLIGHT PASS:** Verified fastboot
  product cactus; flashed Stage49, SHA256
  `49ea5b6c975603b9b0891180f587b53819ca7af3c1ac6c6debd3da1640d7405c`.
  COM25 raw capture
  `../usb-captures/stage-cactus-20261024-162914-151/session-001-162922-958.bin`:
  **76 valid frames**, 4,256 bytes, zero corrupt/lost frames.
  `0x4900=(0x14003380,0,1)` confirms physical OVL0 address mode;
  `0x4901=(1,1,7)` confirms exact FDT carved-out layer1;
  `0x4902=(0xff00ff00,0xffff00ff,1)` proves the test colors
  written to and read from layer1. Actual visible output needs user
  observation. No post-handoff XNU trace arrived. Full findings:
  `shim/TRACE-STAGE48-49.md`.
- **2026-10-24 Stage48 HARDWARE CAPTURE:** 73 valid CLOG v2 frames,
  zero CRC errors and gaps, from
  `../usb-captures/stage-cactus-20261024-143655-403/session-001-143805-303.bin`.
  Handoff prelude, kernel provenance, and WDT disarm (`0x5d -> 0x5c`)
  arrived on host, but **no post-handoff XNU execution record** was
  transmitted. Both active OVL0 sources fall inside FDT reserved
  `0x7f0d0000..0x7fef0000`: L0 `0x7f0d0000`, L1 `0x7f4db000`.
  Hardware scanout sources differ from boot-args FB `0x5e605000`.

- **2026-10-24 Stage47 HARDWARE PASS:** Verified serial
  `<REDACTED_DEVICE_SERIAL>`, fastboot product `cactus`; flashed Stage47
  (SHA256 `3ccea4c45baac845deb082b80e6c00aeb9b71104fb9123849aa1b8f58423c08a`)
  and rebooted with independent COM25 capture running. Raw file
  `../usb-captures/stage-cactus-20261024-140303-742/session-001-140400-979.bin`:
  **212 CRC-valid frames**, 11,872 bytes, zero corruption or gaps;
  strict `--require-combined-stage 47` verifier **PASS**.
  Native XNU EL1 reached intentional **BRK #0xe44** at VA
  `0xfffffff007ac0c68` (ESR_EL1=`0xf2000e44`), confirming the
  next early-C initialization call returned; exception vectors and
  original instructions restored (`0x220b=(1,1,1)`). Watchdog MODE
  was disarmed (`0x5d` to `0x5c`).
  MT6765 OVL0 has two enabled 720x1440 layers: L0 source
  `0x7f0d0000` pitch **2944**, L1 source `0x7f4db000`
  pitch **2880**, L1 format `0x21ff`, offset 0. L1 begins
  exactly 2944*1440 bytes after L0. RDMA0 is in direct-link mode.
  FDT has one RAM bank and 17 reserved ranges; status `0x4704.a=7`
  indicates both candidate source spans are in RAM but neither
  passes the unreserved-range test. The boot_args framebuffer is
  a different address (`0x5e605000`) with 2880-byte stride.
  Active display source addresses may be IOVAs/carveouts; no
  framebuffer writes were attempted. This controlled BRK test
  **does not demonstrate an OS boot or visible framebuffer**.
  Next investigate the OVL/M4U address mapping and progress past
  this checkpoint without a diagnostic BRK.

- **2026-10-24 Stage47 combined next-step image BUILT (subsequently hardware-tested):**
  Keeps Stage45's proven read-only OVL0/RDMA0 scanout registers, adds
  OVL L1 format/alpha, dimensions, offset, pitch, clip, both layer
  address separation, and boot FDT RAM/reserved-memory membership
  classification. All new framebuffer probes are register or FDT
  reads; the code never dereferences these possible IOVAs. In the
  *same boot*, the guarded BRK #0xe44 detects whether XNU returns
  from the next early-C initialization call at
  `0xfffffff007ac0c68`. Stage39 watchdog/COM25 pipeline retained.
  Local WSL build and boot-v2 checks passed; 8 regression tests passed,
  plus the strict combined trace decoder rechecked the 157-frame
  Stage45 hardware capture. Image: `shim/out/cactus/cactus-trace-stage-47-boot.img`,
  45,508,608 bytes, SHA256
  `3ccea4c45baac845deb082b80e6c00aeb9b71104fb9123849aa1b8f58423c08a`.
  Stage47 hardware results are documented above; a full XNU boot
  and visible marker remain unverified.

- **2026-10-24 Stage45 combined native XNU + active display-source
  discovery: hardware PASS.** Flashed checked boot-v2 image
  (SHA256 `8441aa12a94cd29096af823fc63f150df11d417f6e2933bacf087039f2c7e23f`).
  COM25 captured **157 clean frames** at
  `../usb-captures/stage-cactus-20261024-124411-507/session-001-124510-747.bin`,
  with zero corruption, loss, duplicates, or sequence regressions.
  XNU reached the intentional BRK #0xe43 at VA
  **0xfffffff007ac0c64** (ESR_EL1 0xf2000e43), demonstrating it passed
  the next early-C lookup. Stage39 watchdog MODE 0x5d -> 0x5c and
  exception-vector/instruction restoration checks passed.
  Crucially, physical MT6765 OVL0 register snapshots show **enabled
  layers 0 and 1**: L0 source `0x7f0d0000`, pitch **2944** bytes,
  dimensions **720x1440**; L1 source `0x7f4db000`. These addresses
  are separated by exactly 2944*1440 bytes. RDMA0 was enabled in
  direct-link mode (RDMA memory address/pitch zero). The boot-arguments
  framebuffer `0x5e605000` / pitch **2880** does not match active OVL0
  and explains the earlier invisible marker experiment. The guard
  correctly skipped all framebuffer writes. OVL addresses may be
  IOVAs; visible scanout/CPU mapping must still be verified before
  writing to either active buffer. Event-by-event evidence is in
  `shim/TRACE-STAGE45-COMBINED.md`.
  Stage46 checks the return from the next init call at VA
  `0xfffffff007ac0c68` (BRK #0xe44); it is built but **hardware
  untested**.

- **2026-10-24 Stage42 native XNU return confirmed:** COM25 capture
  `../usb-captures/stage-cactus-20261024-112503-583/session-001-112601-430.bin`
  contains **123 valid frames**, zero CRC errors/gaps. ESR=0xf2000e42
  at ELR=0xfffffff007ac0c24, register x0=1. The early boot-argument
  lookup returned successfully. Controlled breakpoint and EL2 restore
  work; next init call remains to be tested by Stage45/46.

- **2026-10-24 Stage40–41 XNU early-C progress (0086+0087 kernel):**
  Stage40 pinned and replaced the first boot-argument lookup call
  (VA 0xfffffff007ac0c20, PA 0x81ac0c20) with a controlled BRK #0xe40.
  Built locally with verified opcode 0x97fe7424; boot image SHA256
  00c4e5e9a78fa11f63a6b2f26a32857d066a2dd3b9d25bb9aecf38e568361c6f.
  Flashed and rebooted successfully. USB capture
  ../usb-captures/stage-cactus-20261024-111103-323/session-001-111156-240.bin
  contained **165 valid frames, no CRC errors or gaps**. Genuine EL1
  0x20a1, BRK exception 0x2206 ESR=0xf2000e40 and ELR=
  0xfffffff007ac0c20, vectors successfully restored 0x220b=(1,1,1).
  Watchdog disable confirmed 0x3900=(0x5d,0x5c,0x2200005c).
  This proves XNU executed further past the original Stage36 C join.
  Stage41 instead trapped at the called boot-argument lookup routine
  entry (VA 0xfffffff007a5dcb0, PA 0x81a5dcb0, opcode 0xd10303ff),
  SHA256 159e0c32603ca41eac4ffdd4cb71bafdb7a4e50f291ee4a226848e33d3e15a2d.
  COM25 capture
  ../usb-captures/stage-cactus-20261024-112044-737/session-001-112131-534.bin
  contained **139 valid frames**, ESR=0xf2000e41 and ELR=
  0xfffffff007a5dcb0. Vector restoration succeeded, watchdog
  disabled. This confirms XNU enters the early boot-argument routine.
  Stage42 later confirmed this function returned successfully; see the
  newer hardware result above.
  These are deliberately stopped native execution checkpoints;
  XNU still has not booted an OS and MI logo scanout remains unverified.

- **2026-10-24 Stage38 watchdog cause confirmed:** Stage38 loaded
  the same rebuilt XNU (0086+0087), stopped at the verified early-C
  BRK, then read MTK RGU at PA 0x10007000. Original RGU MODE=0x5d
  (EN=1), LENGTH=0x5000, STATUS=0. The diagnostic emitted 142
  watchdog-reload 0x3801 events while COM25 stayed on one session
  for the full 180-second watcher window (about 141 seconds since
  connection). Raw capture:
  ../usb-captures/stage-cactus-20261024-104118-353/session-001-104158-129.bin,
  **348 valid 56-byte records, zero CRC errors/gaps/duplicates**.
  Same controlled native XNU checkpoint 0xf2000e24, HVC and restored
  vectors as Stage36. Previous Stage36 resets were ~27 seconds apart.
  RGU servicing eliminates that reset in the controlled hold.
  The Stage38 test accidentally began reloads in early preflight because
  the chainloader does not guarantee a zeroed .bss for C globals.
  Corrected in Stage39 by explicitly initializing watchdog state on entry.
  Stage38 boot image SHA256
  9322e955b9aa4e63e4f966d6a544edc4f822c7a989e81884c2e068f3921a0b1e.

- **2026-10-24 Stage39 full native XNU watchdog handoff:** Same kernel
  and verified pmap_map_bd breakpoint as Stage37. Stage39 services
  the enabled watchdog during preflight and uses the original
  shim/watchdog.c MODE-key sequence just before native XNU handoff.
  COM25 event 0x3900 proves MODE **0x5d -> 0x5c** (EN bit cleared),
  requested write 0x2200005c. The one hardware session under
  ../usb-captures/stage-cactus-20261024-104845-244/
  session-001-104928-737.bin is **58 error-free frames (3248 bytes)**,
  including old pmap BRK arm (0x2500), handoff (0x2303), provenance
  (0x2800), prehandoff flush (0x3500), and successful WDT disarm
  (0x3900). COM25 stayed enumerated for the whole watcher window
  without an observed reset; there were no post-handoff HVC events
  or further USB records. Therefore the MTK RGU watchdog reset
  blocker is resolved, but XNU still has an unlocalized subsequent
  hang/fault, and patch0087's framebuffer mapping outcome remains
  unverified. Stage39 image SHA256
  12655f35745780ae8a799867c0444958c9f4723d1a5200940c1c8e374bcbc8e2.
  Next: place guarded XNU instruction breakpoints after the Stage36
  early-C checkpoint and bisect the first unobserved path. The
  framebuffer scanout path still has no verified visible console.

- **2026-10-24 Stage37 hardware isolation:** Rebuilt XNU with 0086+0087
  continued past the Stage36 deliberate BRK; Stage37 instead armed
  the original pmap_map_bd cold-path breakpoint. Image SHA256
  db46538d2be55ca59aec90dee602bc8600ab577282378d10baeb5f535de36a81.
  The device flashed/rebooted successfully; five COM25 sessions in
  ../usb-captures/stage-cactus-20261024-100153-661 each captured
  48 CRC-valid prehandoff frames, including 0x2500 (old pmap BRK
  installed), 0x2303, 0x2800 and 0x3500. No native XNU or breakpoint
  record was received before the device disconnected again. This is
  inconclusive about 0087, because XNU telemetry queues while USB is
  owned by the shim's EL2 polling loop.

- **2026-10-24 recurring reset insight:** A control image (Stage36)
  returned from its deliberate XNU early-C BRK into the EL2 diagnostic
  hold (events 0x2206, 0x20b3, 0x220b, 0x2308) and still rebooted
  approximately every 26-27 seconds (COM25 open only ~18 seconds).
  The resets thus persist when XNU has stopped and the shim spins
  in drain(1000). The diagnostic loader never calls the full shim's
  watchdog-disable method. MTK top-RGU watchdog at PA 0x10007000
  is a candidate; the reset source remains unproven until RGU state
  and conditional reloads are measured on hardware.

- **2026-10-24 Stage35/Stage36 hardware isolation:** Stage35 was flashed
  successfully. All six COM25 captures under
  ../usb-captures/stage-cactus-20261024-094319-212 contain 47 valid
  frames each, zero errors, and finish with the delivered handoff,
  kernel provenance, and pre-EL1 USB flush markers 0x2303, 0x2800,
  0x3500. The native EL1 signal 0x20a1 is initially queued in RAM and
  requires a return to the USB polling path to be transmitted.
  Absence in Stage35 therefore cannot disprove EL1 execution.
  Stage36 used the identical XNU kernel with patches 0086+0087 and
  installed a reversible BRK #0xe24 at the verified early-C join VA
  0xfffffff007ac0c0c. Its diagnostic image SHA256:
  16369d718bff05c0f2c27efe187669bc9054a0608647c9b0e7c56ea244c894c9.
  Flashed successfully. Captured COM25 session
  ../usb-captures/stage-cactus-20261024-095619-477/session-001-095709-520.bin
  returned 72 valid frames, zero gaps, including genuine EL1 signal
  0x20a1, ESR_EL1 0xf2000e24 and ELR_EL1 0xfffffff007ac0c0c
  at 0x2206, class-1 breakpoint 0x220a, HVC 0x20b3, successful
  restored vectors 0x220b=(1,1,1) and hold 0x2308=(0,1,1).
  Thus patched XNU executes into the verified early-C path and
  EL1-to-EL2 diagnostic handoff works. Deliberate BRK stops further
  execution, so the framebuffer page-table fix remains unverified;
  next isolate the old pmap_map_bd panic join.

- **2026-10-24 Stage34 hardware trial:** product verified `cactus`,
  image SHA256 `a4db4021a6bfc447d0662769a1371135481eedc192f0bef2fb21bccc085493ce`;
  `fastboot flash boot` and `fastboot reboot` succeeded. COM25 watcher
  captured six sessions at
  `../usb-captures/stage-cactus-20261024-091918-246`.
  Sessions 001–005 closed at **44 valid frames (2,464 bytes)** each,
  with no CRC or sequence errors. The events reach the Stage23
  framebuffer RAM readback check `0x2302` and five `0x1902`
  preflight heartbeats, but **not `0x2303` handoff or `0x2800`
  rebuilt-kernel marker**. Therefore this run does **not** verify
  whether patch0087 fixes the XNU framebuffer page-table panic.
  Stage34 build itself remains structurally valid. Investigate why
  device reconnects before the final preflight drain/handoff;
  retain raw COM25 sessions and never interpret their missing
  XNU events as evidence of a new XNU crash.

- **2026-10-24 build update:** Cactus XNU with patches `0086+0087`
  compiled successfully in GitHub Actions `40003701253`. Downloaded
  17,158,000-byte ARM64 kernel SHA256
  `1a0cf300cd5a6f86b5c5ad5a10a0d11bf211e018ffec0dbeb3fa0204c39a15c2`.
  Separate payload `shim/out/cactus/payload-stage28.bin` packed and
  passed relocated kernel entry and pmap instruction guards. Stage34
  build configuration now selects it with original full-height video.
  Stage34 WSL build initially met a tool safety block. On the next
  explicitly authorized attempt it **compiled successfully**, producing
  `shim/out/cactus/cactus-trace-stage-34-boot.img` (45,506,560 bytes,
  SHA256 `a4db4021a6bfc447d0662769a1371135481eedc192f0bef2fb21bccc085493ce`).
  The boot image structure and five targeted regression tests passed.
  **No Stage34 flash or COM25 hardware result:** fastboot detected no
  device at the final check.

- Stage27 GitHub Actions XNU rebuild `39995786681`: **SUCCESS**
  with patch 0086, arm64 cactus Mach-O SHA256
  `a1b8677a3449664fd17a9ee4b3740a76d2d489d0dbf1dce5e4ca5887f3840008`.
  Image build32 flashed successfully but caught the same pmap panic
  with 71 valid USB frames.
- Stage28 **build33** uses the rebuilt XNU plus guarded
  `pmap_map_bd()` pre-panic BRK. Hardware trace
  `../usb-captures/stage-cactus-20261023-235232-019/session-002-235347-971.bin`
  has 78 CRC-valid frames, no errors and strict
  `--require-stage28` PASS. New failing VA
  **`0xfffffff03b000000`**, first framebuffer mapping VA
  `0xfffffff03adbb000`, framebuffer PA
  `0x5e605000..0x5e9fa000`, TTBR1 `0x824c1000`,
  missing L1 slot **`0x824c1e00`** value **zero**.
- Candidate `xnu/patches/0087-cactus-early-io-extent.patch`
  reserves another 16 MiB in the early I/O table allocation range
  (measured overrun 0x1b0000). Applied to local WSL XNU source;
  requires a new CACTUS macOS kernel build + device verification.
- MI logo remains visible, but Stage23 colored RAM markers were not.
  Verify LK `OVL/RDMA` *active scanout* buffer, pitch and format
  before claiming an on-screen XNU console. See
  [Stage28 plan](docs/STAGE28-FRAMEBUFFER-PLAN.md).

## Stage 26 status (2026-10-23)

- **HARDWARE Stage31 FAIL TO ADVANCE:** image flashed/rebooted OKAY;
  `usb-captures/stage-cactus-20261023-224829-332/session-002-224943-912.bin`
  decoded `--require-stage26` PASS, 72 clean COM25 frames, confirms
  temporary 1440→640 height and native EL1 entry. XNU still panics
  through `_pmap_map_bd.cold.1` at `_DebuggerTrapWithState+0x84`
  (`ELR=0xfffffff0072a9e64`, `ESR=0x02000000`). Reduced geometry
  workaround is ineffective. Actual rebuilt kernel with 0086 needed.
  Device absent in post-run fastboot check; use manual fastboot keys.
- Cactus kernel source fix added as
  `xnu/patches/0086-cactus-early-io-l1-tables.patch`. Its aligned
  `init_ptpages()` call allocates missing L1 parent tables for the full
  early framebuffer I/O VA span. Patch applied successfully to local
  `/home/lapdq/xnu-cactus`; the XNU Mach-O has **not** been rebuilt.
- Built `shim/out/cactus/cactus-trace-stage-31-boot.img`, SHA256
  `0ccad55a727f7838fbe93d06ce7729b08d07de6cc3b4927ddc363e37195e0b06`
  (45,506,560 bytes), as an **old-kernel diagnostic bridge**. It
  temporarily reports 640 framebuffer rows before XNU handoff so the
  initial I/O mapping may remain in the original 1 GiB table region.
  COM25 native fault logging remains; Stage25 artificial BRK is absent.
- Local Stage31 build/boot-v2 validation and six Stage22–26 tests PASS.
  No Stage31 hardware test: fastboot was not found earlier, and a later
  tool check was blocked by safety review. See
  [Stage26 detail](shim/TRACE-STAGE26.md).
- Stage26 success gate: **actual XNU code passes the original
  `pmap_map_bd()` mapping failure**; no full boot or visible console
  claimed. The real source fix requires macOS/Xcode build access;
  the GitHub CLI currently reports invalid login credentials.

## Verified current state

- Stock LK boots the Android header-v2 shim; the shim enters XNU at EL1, with MMU enabled during verified checkpoints.
- Live MUSB CDC raw USB logging works through the host's serial port. Binary records have passed CRC, frame order and completeness checks. See [USB logging plan](XNU-USB-LOGGING-PLAN.md).
- Stage 22/build 27 reached a deliberate deeper XNU C checkpoint (54 valid frames).
- Stage 23/build 28 removed that artificial checkpoint; the first genuine XNU synchronous fault reached `_DebuggerTrapWithState`.
- Stage 24/build 29 captured saved XNU registers and resolved the caller to `_pmap_map_bd.cold.1` (two clean hardware captures: 68 and 70 frames).
- **Stage 25/build 30 on hardware PASS**, October 23: captured 77 CRC-valid, complete frames, with zero bad frames or sequence gaps. Verifier: `STAGE25 NULL-PTE REQUEST CAPTURED; COM25 HELD`. A second partial session in the same run is **not** another Stage25 pass.

## Current XNU boot blocker — hardware measured

XNU `pmap_map_bd()` tries to map the display framebuffer across a kernel 1 GiB VA boundary:

| Value | Verified Stage 25 capture |
| --- | --- |
| Physical framebuffer start | `0x5e605000` |
| Exclusive physical end | `0x5e9fa000` |
| Initial requested virtual address | `0xfffffff049dbb000` |
| First failing virtual address | **`0xfffffff04a000000`** |
| Active TTBR1 | `0x824c1000` |
| Missing L1 descriptor slot | **`0x824c1e08`, value `0x0`** |

The immediate issue is the missing early kernel pmap subtree when `io_map` reaches the next VA region. The source-area lead is `osfmk/arm64/arm_vm_init.c` near `va_l1_end` (local XNU sources, not necessarily stored in this Git checkout). Investigate real startup allocation bounds and build **proper** L1/L2/L3 descriptors. Do not fake a descriptor, NOP a debugger trap or skip the panic.

The user sees the **MI logo** during COM25, but did **not** see the Stage 23 three-color test pattern. Framebuffer RAM readback alone does not demonstrate active scanout.

## Most recent proven build and logs

- Image, locally generated and Git-ignored: `shim/out/cactus/cactus-trace-stage-30-boot.img` (45,506,560 bytes).
- SHA-256: `65efa3fdbc9b5e28ca7e3298f9a5ca794939852ebf57a93001f2287d339b155b`.
- Hardware capture remains **outside Git**: `../usb-captures/stage-cactus-20261023-212828-797/session-001-212942-364.bin`.
- Decode it: `python shim/decode-cactus-usb.py "CAPTURE.bin" --require-stage25 --show 90`.
- [Complete event-level proof](shim/TRACE-STAGE25.md) and [historical Cactus notes](docs/CACTUS-BRINGUP-HISTORY.md).

## Next action: Stage 26 (planned, not built)

1. Correct XNU's early virtual space and page-table coverage through the framebuffer mapping (validate against hardware geometry and the memory layout).
2. Rebuild the real XNU Mach-O payload, repack the Android header-v2 shim, and preserve a first-exception COM25 logger.
3. Test in fastboot only once a verified image is prepared. The success gate is XNU execution past the prior `pmap_map_bd` panic. Continue diagnostics for subsequent faults.
4. Separately verify LK display scanout and add a minimal on-screen diagnostic marker/console after a visible framebuffer test succeeds.

## Latest: Stage67 VFS boundary and visible PID1 bar (2026-11-03)

Stage66's native framebuffer remained at STATUS ST56 CPU all initialized
with no visible colored bar. The last observed log
`ktriage_register_subsystem_strings: set subsystem 8 strings` is emitted
inside `decmpfs_init()` called by VFS **inside BSD**, proving BSD entry
has progressed further than earlier diagnostics recognized. Stage67 moves
the bar to visible header row5 (just above STATUS), pins green to an
actual PID1 syscall, and adds checkpoints around `decmpfs_init`,
`nspace_resolver_init`, and the `vfsinit` return. Initial Actions run
41594140727 silently skipped 0101/0102 patches; its output is invalidated.
Corrected patch chain commits `95d0135` and `c15a323`; Actions run
41617481649 **SUCCESS**, with explicit proof all three required patches
applied and `ST67` strings present in the actual compiled Mach-O.
Corrected boot-v2 SHA256
`61677c867d9ee7abb4b7b42704201d8f3bd37929f88293053b19d21f67088bd2`.
Static validation and 16 USB tests passed. Stage67 is **not flashed**.
See `docs/STAGE67-VFS-AND-STATUS.md`.

## Stage65 PID1 proof and bottom framebuffer bar (2026-11-03)

Stage65 CACTUS DEVELOPMENT XNU Actions run `41586007450` succeeded
with patch 0100 (kernel commit `4b70566`). The native framebuffer now
reserves the bottom 16-pixel bar: AMBER until userspace PID1's real `getpid`
syscall, GREEN only after that syscall runs. A new ad-hoc signed ARM64
diagnostic init calls `getpid` before opening `/dev/console`, avoiding a
false negative when console opening fails. The known-good Stage64 GIC
physical addresses remain pinned. Stage65 boot-v2 image was built and
flashed (SHA256 `ae0dc7bf8b061bc022de860d02dff997e667d8d54fca8606c96d7c90373c7837`).
COM25 captured 77 clean frames (14 gaps), with native handoff markers.
Actual green-bar PID1 success **requires owner framebuffer confirmation**;
there is no kernel/userspace execution evidence after the shim handoff in
USB captures. See `docs/STAGE65-PID1-BOOT.md`.

## Stage64 GIC Apple device-tree fix (2026-11-03)

Stage63 reached native XNU but again panicked at `find_gicr_pe_base()`.
Inspection of its *actual embedded* ADT showed the unexpected QEMU GICD/GICR
physical addresses `0x08000000/0x080a0000`, explaining why GICR identity
and affinity tests failed. Stage64 fixes the only GIC `reg` property to
Redmi 6A's independently measured `0x0c000000/0x0c100000`, retaining
Stage63 XNU and all framebuffer/ramdisk pins. Offline guard passed; image
SHA256 `284c88173ed18660027d0eb7ce0e3fb746d5a9475b0b0ce2719435252218ebae`.
Flashed successfully; COM25 recorded 80 clean frames (11 dropped), with
physical GICR census and native XNU handoff markers. Native framebuffer
progress after handoff remains unverified. See `docs/STAGE64-GIC-ADT-FIX.md`.

## Workflow reminders

Windows PowerShell + WSL Ubuntu is the tested host. Many packaging prerequisites and build outputs are **local, ignored files**. `./shim/build_trace_probe.sh 30` is a local WSL shim-image rebuild, while the XNU source itself uses the numbered patch series and `machine_config=CACTUS` in the GitHub workflow. The build script is not a fresh-clone, zero-configuration build.

This repo descended from an older SWEET/Qualcomm port; filenames of source patches and utilities may retain that lineage. Historical SWEET-specific status, UFS assumptions and unrelated iOS GUI claims are excluded from the current Cactus handoff. Never treat the inherited project's results as Cactus hardware evidence.
# Stage51 source status (2026-10-24)

User confirmed Stage49 green/magenta rectangles were visible on
the Redmi 6A panel. Stage51 targets the live LK layer1 at 0x7f4db000:
new XNU patch 0088 supplies a three-block 2MiB framebuffer alias,
and the Cactus Apple ADT/packer now targets that layer. The shim and
decoder accept Stage51 only with its own newly rebuilt kernel payload.
Host tests and patch application checks pass. **Stage51 XNU kernel
compiled in GitHub Actions run 40099595534 and its payload packed**;
Stage51 boot image built with a revision-specific static XNU/ADT guard
and revised runtime checks, SHA256
`b665bd87c63236db8b05fd171cf5a39e4c5c240e96f3318e16e6af29e63e910c`.
**Hardware proven:** Stage51 owner saw the XNU framebuffer
`kprintf startup complete` line. See `shim/TRACE-STAGE51.md`.

# Stage52 kernel/display progress (2026-10-24)

XNU patch 0089 avoids disabling Cactus's early framebuffer console
after the stage20 checkpoint, enables the framebuffer serial backend
for native kprintf and adds Cactarwin banner and detailed init marks
21–37. XNU Actions run 40104893589 **SUCCESS**, SHA256
`945e61817c333218a63c80ca0bd5b237bb95ee4c6724d429ae470c8e9e8a9d36`.
Stage52 boot image validated and flashed, SHA256
`1db5be4481dc79c92b3dc68a26929d2b57a0d3dece606379689a3741c576869a`.
**41 shim tests passed; 79 valid COM25 frames and Stage52 preflight
passed.** Native on-screen progress after handoff is awaiting
observation. See `shim/TRACE-STAGE52.md`.
