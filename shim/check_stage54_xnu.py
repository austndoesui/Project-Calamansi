#!/usr/bin/env python3
"""Fail closed on an unaudited Stage54 CACTUS XNU payload.

The image must contain the separate rebuilt small-font Mach-O, the exact
native bootstrap, an unmodified EL1 exception vector, and LK layer1 ADT.
This is a preflash binary guard, not proof of native runtime progression.
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage51_xnu import (
    NATIVE_PINS, VIRT_BASE, ENTRY_PA, ENTRY_VA, FB_PA,
    FB_STRIDE, FB_W, FB_H, FB_ALIAS_PA, FB_ALIAS_BYTES,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import adt

# Exact Stage54 relocated payload from GitHub Actions run 40118509429.
EXPECTED_SHA256 = "cbf63454264c18cd2398de8e6bbbb36f253743215fdd53572cda454533093e8e"
EXPECTED_ENTRY_C_PA = 0x81AC2A4C
EXPECTED_JOIN_PA = 0x81AC307C
EXPECTED_POST_PA = 0x81AC30D8
EXPECTED_C_PREFIX = (
    0xd10343ff, 0xa9076ffc, 0xa90867fa, 0xa9095ff8,
    0xa90a57f6, 0xa90b4ff4, 0xa90c7bfd, 0x910303fd,
)
EXPECTED_C_BRANCH_PINS = {
    0x81AC2A6C: 0x90000A88,
    0x81AC2A74: 0xD0FFADE1,
    0x81AC2A78: 0x911CE021,
    0x81AC2A94: 0x97E58ABB,
    0x81AC2A98: 0x97E5819E,
    0x81AC2AA8: 0x37F805C9,
    0x81AC2AD8: 0x540029C0,
    0x81AC2B5C: 0x1400012D,
    0x81AC300C: 0x97E57ACD,
    0x81AC3010: 0xB0FFB608,
    0x81AC3068: 0x97E5C5D2,
    0x81AC306C: 0x97E5C295,
    0x81AC3070: 0x97E5C27C,
    0x81AC3074: 0x97E5C5C7,
    0x81AC3078: 0x97E5C5CA,
    EXPECTED_JOIN_PA: 0xD0FFACA1,
    EXPECTED_POST_PA: 0xB0FFB5A8,
}
NATIVE_ENTRY_ASM_PINS = {
    k: v for k, v in NATIVE_PINS.items()
    if k < 0x81A00000
}


def inspect(data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if not EXPECTED_SHA256 or digest != EXPECTED_SHA256:
        raise ValueError("Stage54 payload SHA256 does not match the final audited image")
    p = Payload(data)
    if (p.virt, p.phys, p.mem_size, p.entry, p.segs[0][0]) != (
        VIRT_BASE, 0x80000000, 0x1E000000, ENTRY_VA,
        0xFFFFFFF007004000,
    ):
        raise ValueError("Stage54 XNU virtual/physical bounds or entry changed")
    for pa, word in NATIVE_ENTRY_ASM_PINS.items():
        if p.word(pa) != word:
            raise ValueError(f"Stage54 bootstrap opcode mismatch {pa:#x}")
    if (ENTRY_PA + 4 * (p.word(ENTRY_PA) & 0x03FFFFFF)) != 0x8142F0EC:
        raise ValueError("Stage54 native branch target changed")
    if (0x8142F3E4 + 4 * (p.word(0x8142F3E4) & 0x03FFFFFF)) != 0x81433F84:
        raise ValueError("Stage54 MMU TTBR0 helper target changed")
    for pa in (0x81429000, 0x81429200):
        if struct.unpack("<4I", p.read(pa, 16)) != (
            NATIVE_PINS[pa], 0xD503201F, 0xD503201F, 0xD503201F,
        ):
            raise ValueError("Stage54 native EL1 exception vector changed")
    if tuple(p.word(EXPECTED_ENTRY_C_PA + i * 4)
             for i in range(len(EXPECTED_C_PREFIX))) != EXPECTED_C_PREFIX:
        raise ValueError("Stage54 early C prologue moved")
    if not EXPECTED_C_BRANCH_PINS:
        raise ValueError("Stage54 C continuation pins have not been audited")
    for pa, word in EXPECTED_C_BRANCH_PINS.items():
        if p.word(pa) != word:
            raise ValueError(f"Stage54 early C opcode mismatch at {pa:#x}")
    if any(p.read(0x8117A000, 0x4000)):
        raise ValueError("Stage54 bootstrap page-table pool not zero")
    if p.qword(0x81178A18) != 0x22A5192519:
        raise ValueError("Stage54 TCR constant changed")
    if p.word(0x81004018) & 0x80000000:
        raise ValueError("Stage54 Mach-O relocation flag changed")
    if not (FB_ALIAS_PA <= FB_PA and
            FB_PA + FB_H * FB_STRIDE <= FB_ALIAS_PA + FB_ALIAS_BYTES and
            0x7F0D0000 <= FB_PA and
            FB_PA + FB_H * FB_STRIDE <= 0x7FEF0000):
        raise ValueError("Stage54 framebuffer outside reserved LK scanout")
    root, end = adt.parse(data[p.adt_offset:p.adt_offset + p.adt_size])
    nodes = [node for node in root.children if node.name == "sweet-fbcon"]
    if end != p.adt_size or len(nodes) != 1:
        raise ValueError("Stage54 ADT frame buffer missing")
    if struct.unpack("<QQ", nodes[0].prop("reg")) != (FB_PA, FB_H * FB_STRIDE):
        raise ValueError("Stage54 fbcon physical address/size incorrect")
    for key, size in (("width", FB_W), ("height", FB_H), ("stride", FB_STRIDE)):
        if struct.unpack("<I", nodes[0].prop(key))[0] != size:
            raise ValueError(f"Stage54 ADT {key} mismatch")
    return {
        "sha256": digest,
        "entry_va": hex(p.entry),
        "entry_c_pa": hex(EXPECTED_ENTRY_C_PA),
        "join_pa": hex(EXPECTED_JOIN_PA),
        "post_pa": hex(EXPECTED_POST_PA),
        "fb_pa": hex(FB_PA),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE54 XNU/ADT GUARD PASS", inspect(args.payload.read_bytes()))
