# Stage95 — native XNU guard correction and hardware retest (2026-11-09)

The iPhone X iOS 16.7.16 GUI/dyld kernel from successful CI run
`42581634328` is unchanged (SHA256
`66d7e63cfd396c2cb16738418d10e6878875a395af0ef6f716fed882b42b4ff8`).
The 16 GiB native iOS userdata filesystem is also unchanged.

## Root cause of Stage94 recovery reboot

Stage94 copied all 11 native XNU segments and prepared valid boot arguments,
but returned `0x510` at `stage20b_arm()`. Its shim still required five old
Stage91 instructions, despite the Stage94 XNU kernel recompilation changing
those words. USB captured 56 error-free pre-handoff frames, then the shim
returned to TWRP before transferring execution to native XNU.

## Stage95 correction

The shim has an explicit Stage95 C guard profile with the five instructions
from the SHA-pinned CI Mach-O at `0x81abfdfc`, `0x81abfe1c`, `0x81abfe24`,
`0x81abfe2c` and `0x81ac042c`, matching the relocated payload at each
physical address. The Stage48 framebuffer opcode check also uses the new
word. `shim/check_stage95_shim_guards.py` checks the source SHA, each opcode
in both representations and all five shim C guard branches during the build,
before the boot image is packaged. All 41 original native root, GIC,
framebuffer and startup guards also pass.

`shim/out/cactus/cactus-trace-stage-95-boot.img`: 62,283,776 bytes,
SHA256 `f7686c393be19d6cc7398ee9ccd9d48318aadc0c3bcfca9d9a4f2ac99eda70f7`.
Only the boot partition was flashed, on `3184a8a17d2b`, successfully.

## Measured hardware result

Captured `usb-captures/stage-cactus-20261109-134251-144/session-001-134301-848.bin`:

- 91 valid COM25 frames, zero corrupt frames, zero gaps or duplicates.
- `0x4802` verified Stage95's framebuffer opcode: `0x913a5400`.
- `0x2303` native entry preparation, `0x2800` exact kernel provenance,
  `0x3500` native XNU handoff and `0x3900` completion all present, in order.
- `python shim/decode-cactus-usb.py ... --require-stage95` reports **PASS**.

**Limitation:** COM25 proves pre-XNU handoff only; it does not capture
Apple launchd, dyld or SpringBoard running. Native framebuffer evidence is
needed to determine whether the Stage94 GUI and dyld changes advance iOS.
