# Stage54: IOKit lockdown and BSD boundary — built, not hardware tested

2026-10-24. Stage53 physically showed native XNU through IOKit platform
initialization, ending at the **before-call** `PE_lockdown_iokit` marker.
Stage54 keeps the proven LK OVL0 layer1 framebuffer at `0x7f4db000`,
retains the compact 8x16 XNU console and adds these distinct CACTUS-only
progress markers without bypassing native initialization:

- `ST54 PE_lockdown_iokit enter` / `done` in `osfmk/kern/startup.c`.
- `ST54 zalloc_iokit_lockdown enter` / `done` in `pexpert/arm/pe_init.c`.
- `ST54 StartIOKitMatching enter` / `done` in `pexpert/arm/pe_init.c`.
- `ST54 vm_set_restrictions enter` / `done`, with actual
  `machine_info.max_cpus`, in `osfmk/kern/startup.c`.
- `ST54 BSD entry boundary`; Stage53's existing `bsd_init enter` and
  per-phase BSD markers are still enabled.

Source patch `xnu/patches/0091-cactus-iokit-bsd-stage54.patch` was
generated with `tools/stage54_generate_patch.py` and committed on isolated
branch `stage54-cactus-bsd`, commit `7bc3bbd`. GitHub Actions run
`40118509429` (CACTUS DEVELOPMENT) **succeeded**. Original kernel
`../stage54-kernel-run40118509429/xnu-kernel/kernel.development.cactus`
(17,158,168 bytes) SHA256:

`ed5123cee5377846b6485572f0594cedb1d08f8ec4ba65c68616e17fabbda81d`

Stage54's source additions shift native C `arm_init` by `+0x150` bytes
relative to Stage53. Static guard and shim pin exact new arm_init prologue,
follow-on calls, C checkpoint PA `0x81ac30d8` opcode `0xb0ffb5a8`,
native EL1 vectors and page table initialization. Early assembly entry
remains PA `0x8142d488`. New USB prehandoff marker `0x5400` identifies
the exact compiled kernel SHA prefix; `0x2800` carries the same identity.

The repacked relocated XNU payload SHA256 is:

`cbf63454264c18cd2398de8e6bbbb36f253743215fdd53572cda454533093e8e`

**Ready boot image:**

`shim/out/cactus/cactus-trace-stage-54-boot.img`

Size 45,524,992 bytes; SHA256:

`c1c5fe8c342ab2049e0d4daa47b483f6754498eb6b3b36fb18ce6af235e446f6`

Built in Ubuntu via `./shim/build_trace_probe.sh 54`; `check_image.py`,
stage-specific SHA/native-instruction/ADT verifier, and the 43 shim unit
tests passed. Git diff whitespace check passed (pre-existing CRLF warning).

**Hardware status:** Stage54 has **not** been flashed or observed on the
phone. At preparation time `fastboot devices -l` showed no device. Once
the cactus fastboot serial is confirmed, run the guarded Windows runner:

`powershell -NoProfile -ExecutionPolicy Bypass -File "F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1" -Stage 54 -CaptureSeconds 120`

The runner verifies boot SHA256, exact device product and serial, then
starts USB capture *before* flashing. Its decoder validates `0x5400` and
native checkpoint; these **pre-handoff markers cannot prove post-handoff
XNU progress**. Use the physical framebuffer to identify the last
`ST54 ...` status, particularly whether IOKit matching returns and BSD
initialization begins. The iPhone X 16.7.16 IPSW is locally verified but
not needed to test Stage54; `rd=md0`/PID 1 is subsequent work.
