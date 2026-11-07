#!/usr/bin/env python3
"""Stage52 exact binary/ADT check for the rebuilt CACTUS native console.

Retains all Stage51 checks for the old kernel. Stage52's __TEXT increased
by 0x3000; pin the actual rebuilt kernel instructions at their new PAs.
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage51_xnu import (
    NATIVE_PINS, VIRT_BASE, FB_PA, FB_STRIDE, FB_W, FB_H,
    FB_ALIAS_PA, FB_ALIAS_BYTES,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import adt

SHA256 = "4fff93ad4d6a8b24da6d7ff3538d6497a490afc1ee2353b3bbe33f087b28864a"
ENTRY_PA = 0x81430488
ENTRY_VA = 0xFFFFFFF007430488
SHIFT = 0x3000

# Specific instruction values changed by Stage52's additional arm_init
# progress markers and larger __TEXT section. Other pinned opcodes still
# equal their Stage51 values after relocating by 0x3000.
REVISED = {
    0x8142F154: 0x90FFEA59,
    0x81AC0628: 0x9136F021,
    0x81AC0644: 0x97E5877F,
    0x81AC0C2C: 0xD0FFACA1,
    0x81AC0C84: 0x97DF9F3F,
    0x81AC0C88: 0xB0FFB5A8,
}


def inspect(data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        raise ValueError("Stage52 payload SHA256 does not match verified CI build")
    p = Payload(data)
    if (p.virt, p.phys, p.mem_size, p.entry, p.segs[0][0]) != (
        VIRT_BASE, 0x80000000, 0x1E000000, ENTRY_VA,
        0xFFFFFFF007004000,
    ):
        raise ValueError("Stage52 XNU virtual/physical layout changed")
    for old_pa, old_opcode in NATIVE_PINS.items():
        address = old_pa + SHIFT
        want = REVISED.get(old_pa, old_opcode)
        got = p.word(address)
        if got != want:
            raise ValueError(
                f"Stage52 native opcode mismatch at {address:#x}: "
                f"{got:#x} != {want:#x}"
            )
    if ENTRY_PA + 4 * (p.word(ENTRY_PA) & 0x3FFFFFF) != 0x814320EC:
        raise ValueError("Stage52 entry branch target no longer matches")
    for old_pa in (0x81429000, 0x81429200):
        v = struct.unpack("<4I", p.read(old_pa + SHIFT, 16))
        if v != (NATIVE_PINS[old_pa], 0xD503201F, 0xD503201F, 0xD503201F):
            raise ValueError("Stage52 real XNU exception vector changed")
    if p.qword(0x81178A18) != 0x22A5192519:
        raise ValueError("Stage52 TCR changed")
    if any(p.read(0x8117A000, 0x4000)):
        raise ValueError("Stage52 page table pool is nonzero")
    if p.word(0x81004018) & 0x80000000:
        raise ValueError("Stage52 XNU startup RAM flags changed")
    if not (FB_ALIAS_PA <= FB_PA and
            FB_PA + FB_H * FB_STRIDE <= FB_ALIAS_PA + FB_ALIAS_BYTES and
            0x7F0D0000 <= FB_PA and FB_PA + FB_H * FB_STRIDE <= 0x7FEF0000):
        raise ValueError("Stage52 live framebuffer exceeds the reserved range")
    root, end = adt.parse(data[p.adt_offset:p.adt_offset + p.adt_size])
    nodes = [n for n in root.children if n.name == "sweet-fbcon"]
    if end != p.adt_size or len(nodes) != 1:
        raise ValueError("Stage52 Apple device-tree framebuffer missing")
    fb = nodes[0]
    if struct.unpack("<QQ", fb.prop("reg")) != (FB_PA, FB_H * FB_STRIDE):
        raise ValueError("Stage52 console address/length mismatch")
    for key, expected in (("width", FB_W), ("height", FB_H),
                          ("stride", FB_STRIDE)):
        if struct.unpack("<I", fb.prop(key))[0] != expected:
            raise ValueError(f"Stage52 console {key} mismatch")
    return {"sha256": digest, "entry_pa": hex(ENTRY_PA),
            "late_c_pa": "0x81ac3c2c",
            "exception_vectors": ["0x8142c000", "0x8142c200"],
            "fb_pa": hex(FB_PA)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE52 REBUILT XNU/ADT GUARD PASS", inspect(args.payload.read_bytes()))


if __name__ == "__main__":
    main()
