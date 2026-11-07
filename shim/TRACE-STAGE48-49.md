# Stage 48–49: Uninterrupted XNU and Cactus LK framebuffer

Stage 48 eliminates both deliberate stop points used for early-C
initialization and the pmap panic sentinel. The rebuilt XNU payload
remains the Stage28 image with source fixes 0086 and 0087. The shim
keeps the EL1 synchronous exception recorder, Stage35 COM25 handoff
flush and Stage39 watchdog disarm. The boot attempt is intentionally
unbounded; normal XNU startup does not poll COM25 after EL1 handoff.

## Stage48 hardware evidence (2026-10-24)

- Boot image: `out/cactus/cactus-trace-stage-48-boot.img`,
  45,508,608 bytes,
  SHA256 `94aa7f91fb240b467ca433ec06a617edc4e7146dbac70050549c5306a5a0187d`.
- The fastboot target was verified as `cactus`; flash and reboot succeeded.
- Raw COM25 file:
  `../../usb-captures/stage-cactus-20261024-143655-403/session-001-143805-303.bin`.
  Exactly **73 valid CLOG v2 frames**, zero corrupt, unmatched, gaps,
  duplicates or sequence regressions.
- Handoff prelude `0x2303`, rebuilt-kernel ID `0x2800`, Stage35
  flush `0x3500` and Stage39 RGU watchdog disarm `0x3900` arrived
  on the host. The RGU MODE register changed `0x5d -> 0x5c`.
  No `0x20a1` native-EL1 record or genuine exception returned to the
  USB service after that. A silent COM25 session does **not** prove a
  panic or successful full XNU boot: XNU owns execution after handoff.
- `0x4802` proved early-C instruction at PA `0x81ac0c68` was the
  original `0x90ffb5c8`, not the old synthetic `BRK`.

The inherited LK scanout has OVL0 L0 and L1 active. Read-only DDP
registers identify L0 source `0x7f0d0000` with a 2944-byte pitch,
L1 source `0x7f4db000` with a 2880-byte pitch; each source represents
a 720 x 1440 plane. RDMA0 is in direct-link mode. The FDT memory
inspection found reserved region **`0x7f0d0000..0x7fef0000`**
(size `0xe20000`); `0x4801` shows that both layer source spans lie
inside it. XNU `boot_args.Video.v_baseAddr` is still `0x5e605000`,
so previous writes to that boot-args buffer could not prove panel
scanout.

## Stage49 hardware preflight — PASS (2026-10-24)

Image:
`out/cactus/cactus-trace-stage-49-boot.img`
size 45,508,608 bytes,
SHA256 `49ea5b6c975603b9b0891180f587b53819ca7af3c1ac6c6debd3da1640d7405c`.
The 0086+0087 XNU loader guards, late-C exact-instruction guard,
Android boot v2 packaging, and 11 targeted Python regression tests
pass (including the Stage49 decoder tests).

Verified fastboot product cactus, then flashed and rebooted Stage49.
The independent COM25 watcher captured
`../../usb-captures/stage-cactus-20261024-162914-151/session-001-162922-958.bin`:
4,256 bytes, **76 CRC-valid frames**, zero sequence gaps or corruption.
Strict `--require-stage49` reports **PREFLIGHT PASS**.
Hardware record `0x4900=(0x14003380,0,1)` confirms physical OVL0
addresses; `0x4901=(1,1,7)` confirms the exact reserved carveout,
and `0x4902=(0xff00ff00,0xffff00ff,1)` verifies the two-color
layer1 pixel write/readback. Visible panel output remains unverified.
**Subsequent user confirmation:** the green and magenta test rectangles
were visible near the top of the physical Redmi 6A screen. Stage49
therefore proves actual layer1 scanout, beyond RAM readback.
The last received XNU-handoff-related marker was WDT disarm; no
post-EL1 progress message reached the COM25 host.

Before XNU handoff, read `0x14003380` (MT6765 SMI LARB0
`NON_SEC_CON`, bit0 is OVL0 MMU enable), emit `0x4900`, and emit
`0x4901` for the framebuffer safety result. Only when the OVL0 port
is in physical mode, the exact FDT reserved area exists, and both
layer addresses, pitches, dimensions, enables and configuration
registers match the observed Stage48 hardware does the shim write
160x48 green/magenta pixels into a small area of layer1, clean its
data cache lines and emit `0x4902` with readback values. If any
condition is false, the write is skipped. A passing write readback
alone still does not prove the display shows those pixels.

To repeat Stage49, start the independent COM25 watcher before flashing,
then use:

```powershell
fastboot -s <REDACTED_DEVICE_SERIAL> getvar product
fastboot -s <REDACTED_DEVICE_SERIAL> flash boot 'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\out\cactus\cactus-trace-stage-49-boot.img'
fastboot -s <REDACTED_DEVICE_SERIAL> reboot
```

Once the watcher has closed its raw session file:

```powershell
python shim/decode-cactus-usb.py 'FULL_PATH_TO_SESSION.bin' --require-stage49 --show 100
```

Interpret the result before changing XNU `boot_args.Video`. If
`0x4901.a=1` and `0x4902.c=1`, the RAM write succeeded; human
observation determines whether the colors reached the panel. If
`0x4901.a=0`, use the MMU setting and DT reserved mapping to guide
the next display-specific change. Independently, native XNU progress
past the previous Stage47 checkpoint needs an EL1-to-EL2 returnable
logging hook; a COM25 stream that ends on `0x3900` cannot determine
the deepest XNU initialization call reached.

## Stage50 built for the next flash

Stage49 proved physical layer1 CPU access, so Stage50 keeps all of its
exact guards and only after a successful color readback sets XNU
`boot_args.Video.v_baseAddr` from `0x5e605000` to
`0x7f4db000`. The measured dimensions remain 720x1440 with
2880-byte row pitch. Marker `0x5000` proves the guarded redirection
occurred; `0x50ee` indicates an ABI mismatch. No synthetic XNU
breakpoint is reintroduced, and the COM25 exception handler remains.

Local WSL image `out/cactus/cactus-trace-stage-50-boot.img`:
45,508,608 bytes, SHA256
`3db03add61280050e03d83c9c84c1803799e06db8428915dfda25798c04f43b0`.
Boot-v2 validation and Stage27/28/44 instruction guards passed;
targeted Python tests passed. Stage50 is **not hardware tested** yet.
Run on the next fastboot opportunity with the automatic runner:
`powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\ROM\patching\redmi 6a xnu\ios-cactus\shim\run-stage49.ps1' -Stage 50 -CaptureSeconds 105`.
The runner verifies image hash and fastboot product, captures COM25
before flashing, and checks the trace with `--require-stage50`.

## Next XNU console work (after Stage50)

Stage50 changes only `boot_args.Video.v_baseAddr`; it does not install
an XNU character-output hook or cause normal XNU execution to keep
pumping USB after the EL1 handoff. Moreover, `tools/mkadt.py` still
generates the Cactus `sweet-fbcon` ADT node at `0x5e605000`, and the
compiled XNU's Cactus early-console VA/PA alias in
`xnu/patches/0082-cactus-machine-config.patch` also maps the old
`0x5e605000` region. Neither points at the verified live layer1
`0x7f4db000`. Correct both paths in a new Cactus XNU build before
expecting `kprintf`/early panic messages on the physical panel. Take
care to cover the entire 720x1440x32 buffer (2880-byte stride) with
the post-MMU alias, retain the reserved display carveout, and validate
the existing `sweet-fbcon` registration/console activation. Then add
a returnable EL1-to-EL2 progress/log transport if COM25 must stay live
after XNU takes control. Screen output and USB capture are separate
hardware success gates; neither guarantees full XNU startup.
