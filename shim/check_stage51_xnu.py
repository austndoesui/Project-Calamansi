#!/usr/bin/env python3
"""Static guard for the Stage51 XNU kernel and its live LK layer1 ADT.

Stage28's exact-opcode profile was for a different XNU Mach-O. Pin the
*relocated* Stage51 payload and check the relevant native instructions,
exception vectors, framebuffer alias and ADT before packing a boot image.
This cannot prove actual EL1 execution, display output, or USB logging.
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

from check_stage21b_mmu import Payload

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import adt

EXPECTED_SHA256 = "9245a8e01f567a6a08b83a148ce5c1b044d684269962e00a84ae60856fe21c42"
VIRT_BASE = 0xFFFFFFF006000000
ENTRY_VA = 0xFFFFFFF00742D488
ENTRY_PA = 0x8142D488
FB_PA, FB_STRIDE, FB_W, FB_H = 0x7F4DB000, 2880, 720, 1440
FB_ALIAS_PA, FB_ALIAS_BYTES = 0x7F400000, 3 * 0x200000

# The Stage51 kernel inserted a third L2 block descriptor (+12 bytes in
# the early bootstrap) and shifted the C entry by 32 bytes. These are
# *actual* relocated Mach-O instructions, not guessed source offsets.
NATIVE_PINS = {
    ENTRY_PA: 0x14000719,       # b 0x8142f0ec
    0x8142F0EC: 0xD510109F,  # early EL1 startup
    0x8142F0F8: 0xD2800015,
    0x8142F154: 0xF0FFEA59,
    0x8142F174: 0xD50041BF,  # SPSel=1
    0x8142F18C: 0xD50040BF,  # SPSel=0
    0x8142F1CC: 0x36F80161,
    0x8142F220: 0xD355FF05,
    0x8142F378: 0xF90000C8,  # alias PTE write
    0x8142F3B4: 0xF82C784B, # new L2 descriptor store
    0x8142F3C0: 0xF82C784B, # third L2 descriptor store
    0x8142F3D8: 0xD5182041, # MSR TCR_EL1
    0x8142F3E4: 0x940012E8, # TTBR0 helper call
    0x8142F3F4: 0xD5182020, # MSR TTBR1_EL1
    0x8142F43C: 0xD518A200, # MSR MAIR_EL1
    0x8142F45C: 0xB40000B5, # branch by startup path
    0x8142F480: 0xD518C000, # MSR VBAR_EL1
    0x8142F494: 0xD5181000, # MSR SCTLR_EL1
    0x8142F498: 0xD5033FDF, # ISB after MMU enable
    0x8142F4B0: 0x8B160280, # boot_args VA computation
    0x81433F88: 0xD5182000, # helper: MSR TTBR0_EL1
    0x81AC05FC: 0xD10343FF, # entry C stack prologue
    0x81AC0628: 0x913CF021,
    0x81AC0644: 0x97E5937F, # Stage27 C continuation call
    0x81AC0C2C: 0xB0FFACC1, # Stage22 C join
    0x81AC0C40: 0x97FE7424, # first boot-argument lookup
    0x81AC0C84: 0x97DFAB3F, # platform initialization call
    0x81AC0C88: 0x90FFB5C8, # first instruction after init call
    0x81429000: 0x14000400, # EL1t synchronous vector
    0x81429200: 0x140003F6, # EL1h synchronous vector
}


def inspect(data: bytes) -> dict:
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != EXPECTED_SHA256:
        raise ValueError("Stage51 relocated XNU payload hash does not match audited build")
    p = Payload(data)
    if (p.virt, p.phys, p.mem_size, p.entry, p.segs[0][0]) != (
        VIRT_BASE, 0x80000000, 0x1E000000, ENTRY_VA,
        0xFFFFFFF007004000
    ):
        raise ValueError("Stage51 payload physical/virtual memory layout changed")
    for pa, value in NATIVE_PINS.items():
        actual = p.word(pa)
        if actual != value:
            raise ValueError(f"Stage51 XNU opcode changed at {pa:#x}: {actual:#x} != {value:#x}")
    if any(p.read(0x8117A000, 0x4000)):
        raise ValueError("Stage51 bootstrap page-table pool is not zero-initialized")
    if p.qword(0x81178A18) != 0x22A5192519:
        raise ValueError("Stage51 TCR_EL1 value changed")
    if p.word(0x81004018) & 0x80000000:
        raise ValueError("Stage51 Mach-O RAM relocation flags changed")
    if not (FB_ALIAS_PA <= FB_PA and FB_PA + FB_H * FB_STRIDE <=
            FB_ALIAS_PA + FB_ALIAS_BYTES and
            0x7F0D0000 <= FB_PA and FB_PA + FB_H * FB_STRIDE <= 0x7FEF0000):
        raise ValueError("Stage51 framebuffer outside 3-block alias / FDT reservation")
    if (ENTRY_PA + 4 * (p.word(ENTRY_PA) & 0x03FFFFFF)) != 0x8142F0EC:
        raise ValueError("Stage51 entry no longer branches to early XNU")
    if (0x8142F3E4 + 4 * (p.word(0x8142F3E4) & 0x03FFFFFF)) != 0x81433F84:
        raise ValueError("Stage51 TTBR0 helper branch moved")
    for pa in (0x81429000, 0x81429200):
        if tuple(struct.unpack("<4I", p.read(pa, 16))) != (
            NATIVE_PINS[pa], 0xD503201F, 0xD503201F, 0xD503201F
        ):
            raise ValueError("Stage51 synchronous exception vector changed")
    root, consumed = adt.parse(data[p.adt_offset:p.adt_offset + p.adt_size])
    nodes = [c for c in root.children if c.name == "sweet-fbcon"]
    if consumed != p.adt_size or len(nodes) != 1:
        raise ValueError("Stage51 Apple ADT console missing or malformed")
    node = nodes[0]
    if struct.unpack("<QQ", node.prop("reg")) != (FB_PA, FB_H * FB_STRIDE):
        raise ValueError("Stage51 ADT fbcon uses wrong scanout address")
    for name, expected in (("width", FB_W), ("height", FB_H), ("stride", FB_STRIDE)):
        if struct.unpack("<I", node.prop(name))[0] != expected:
            raise ValueError(f"Stage51 ADT console {name} mismatch")
    return {"payload_sha256": actual_sha, "entry_pa": ENTRY_PA,
            "mmu_enable_pa": 0x8142F494,
            "vectors": (0x81429000, 0x81429200),
            "c_join": 0x81AC0C2C, "fb_phys": FB_PA,
            "fb_alias": (FB_ALIAS_PA, FB_ALIAS_BYTES)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    report = inspect(args.payload.read_bytes())
    print("STAGE51 REBUILT XNU/ADT STATIC GUARD PASS", report)
    print("NOTE: static payload inspection cannot establish hardware boot or native XNU output")


if __name__ == "__main__":
    main()
