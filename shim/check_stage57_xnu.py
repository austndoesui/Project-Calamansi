#!/usr/bin/env python3
"""Fail closed on the exact Stage57 CACTUS XNU + RAMDisk boot payload.

Asserts C entry, late C join, native MMU, ADT RAMDisk relocation, LK fb,
and the signed diagnostic PID 1. Compilation does not prove BSD/PID1 ran.
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
import mkpayload

EXPECTED_SHA256 = "e2970174ed89542d4752a037f849526f7fc11d968130f2ccf8c9bded213c804f"
EXPECTED_INIT_SHA256 = "d187f6f1529b9290dfcd64d6923ce2a59e30f6d9fdb463970728744d806e9991"
EXPECTED_ENTRY_C_PA = 0x81AC2D3C
EXPECTED_JOIN_PA = 0x81AC336C
EXPECTED_POST_PA = 0x81AC33C8
EXPECTED_C_PREFIX = (
    0xd10343ff, 0xa9076ffc, 0xa90867fa, 0xa9095ff8,
    0xa90a57f6, 0xa90b4ff4, 0xa90c7bfd, 0x910303fd,
)
EXPECTED_C_BRANCH_PINS = {
    0x81AC2D5C: 0x90000A88,
    0x81AC2D64: 0xD0FFADE1,
    0x81AC2D68: 0x9113B821,
    0x81AC2D84: 0x97E589FF,
    0x81AC2D88: 0x97E580E2,
    0x81AC2D98: 0x37F805C9,
    0x81AC2DC8: 0x540029C0,
    0x81AC2E4C: 0x1400012D,
    0x81AC32FC: 0x97E57A11,
    0x81AC3300: 0xB0FFB608,
    0x81AC3358: 0x97E5C522,
    0x81AC335C: 0x97E5C1E5,
    0x81AC3360: 0x97E5C1CC,
    0x81AC3364: 0x97E5C517,
    0x81AC3368: 0x97E5C51A,
    EXPECTED_JOIN_PA: 0xB0FFACA1,
    EXPECTED_POST_PA: 0xB0FFB5A8,
}


def inspect(data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Stage57 relocated payload SHA256 differs from audited build")
    p = Payload(data, expected_segments=11)
    if (p.virt, p.phys, p.mem_size, p.entry, p.segs[0][0]) != (
        VIRT_BASE, 0x80000000, 0x1E000000, ENTRY_VA,
        0xFFFFFFF007004000,
    ):
        raise ValueError("Stage57 XNU virtual/physical layout changed")
    for pa, word in NATIVE_PINS.items():
        if pa == 0x81433F88:
            continue  # Native TTBR0 helper moved +0x30 in Stage57.
        if pa == 0x8142F3E4:
            word = 0x940012F4
        if pa < 0x81A00000 and p.word(pa) != word:
            raise ValueError(f"Stage57 native bootstrap opcode mismatch {pa:#x}")
    if ENTRY_PA + 4 * (p.word(ENTRY_PA) & 0x03FFFFFF) != 0x8142F0EC:
        raise ValueError("Stage57 native branch target changed")
    if 0x8142F3E4 + 4 * (p.word(0x8142F3E4) & 0x03FFFFFF) != 0x81433FB4:
        raise ValueError("Stage57 native TTBR0 helper changed")
    if p.word(0x81433FB8) != 0xD5182000:
        raise ValueError("Stage57 native TTBR0 MSR changed")
    for pa in (0x81429000, 0x81429200):
        if struct.unpack("<4I", p.read(pa, 16)) != (
            NATIVE_PINS[pa], 0xD503201F, 0xD503201F, 0xD503201F,
        ):
            raise ValueError("Stage57 native EL1 exception vector changed")
    if tuple(p.word(EXPECTED_ENTRY_C_PA + 4 * i)
             for i in range(len(EXPECTED_C_PREFIX))) != EXPECTED_C_PREFIX:
        raise ValueError("Stage57 early C entry prologue changed")
    for pa, word in EXPECTED_C_BRANCH_PINS.items():
        if p.word(pa) != word:
            raise ValueError(f"Stage57 early C opcode mismatch {pa:#x}")
    if any(p.read(0x8117A000, 0x4000)):
        raise ValueError("Stage57 native bootstrap page table pool nonzero")
    if p.qword(0x81178A18) != 0x22A5192519:
        raise ValueError("Stage57 native TCR changed")
    if p.word(0x81004018) & 0x80000000:
        raise ValueError("Stage57 native Mach-O relocation flag changed")
    if not (FB_ALIAS_PA <= FB_PA and
            FB_PA + FB_H * FB_STRIDE <= FB_ALIAS_PA + FB_ALIAS_BYTES and
            0x7F0D0000 <= FB_PA and
            FB_PA + FB_H * FB_STRIDE <= 0x7FEF0000):
        raise ValueError("Stage57 framebuffer outside reserved LK scanout")
    root, end = adt.parse(data[p.adt_offset:p.adt_offset + p.adt_size])
    if end != p.adt_size:
        raise ValueError("Stage57 device tree includes trailing data")
    fb = [n for n in root.children if n.name == "sweet-fbcon"]
    if len(fb) != 1 or struct.unpack("<QQ", fb[0].prop("reg")) != (
        FB_PA, FB_H * FB_STRIDE
    ):
        raise ValueError("Stage57 native fbcon physical framebuffer changed")
    for key, size in (("width", FB_W), ("height", FB_H), ("stride", FB_STRIDE)):
        if struct.unpack("<I", fb[0].prop(key))[0] != size:
            raise ValueError(f"Stage57 framebuffer {key} changed")
    chosen = [n for n in root.children if n.name == "chosen"]
    if len(chosen) != 1:
        raise ValueError("Stage57 ADT missing chosen")
    maps = [n for n in chosen[0].children if n.name == "memory-map"]
    if len(maps) != 1:
        raise ValueError("Stage57 ADT missing memory map")
    rd_ptr = maps[0].prop("RAMDisk")
    if rd_ptr is None or len(rd_ptr) != 16:
        raise ValueError("Stage57 RAMDisk pointer absent")
    rd_pa, rd_sz = struct.unpack("<QQ", rd_ptr)
    rd = p.segs[-1]
    seg_pa = p.phys + rd[0] - p.virt
    if (rd_pa, rd_sz, seg_pa, rd[1], rd[3]) != (
        0x824BC000, 0x8000, 0x824BC000, 0x8000, 0x40FB,
    ):
        raise ValueError("Stage57 RAMDisk ADT pointer or segment layout changed")
    if (rd_pa & 0x3fff or rd_sz & 0x3fff or
            rd_pa < p.phys or rd_pa + rd_sz > p.phys + p.mem_size):
        raise ValueError("Stage57 RAMDisk is not aligned/reserved within XNU RAM")
    signed_init = data[rd[2]:rd[2] + rd[3]]
    if hashlib.sha256(signed_init).hexdigest() != EXPECTED_INIT_SHA256:
        raise ValueError("Stage57 signed init program changed")
    if struct.unpack_from("<2I", signed_init) != (0xFEEDFACF, 0x0100000C):
        raise ValueError("Stage57 root is not a signed arm64 Mach-O")
    command_line = data[mkpayload.CMDLINE:mkpayload.SEG_TABLE].split(b"\0", 1)[0]
    if command_line != b"debug=0xc rd=md0":
        raise ValueError("Stage57 root boot arguments do not select md0")
    # boot_args is placed after the whole kernel, RAMDisk, then ADT, at 16K alignment.
    ba_pa = (p.phys + p.kernel_end - p.virt + p.adt_size + 0x3FFF) & ~0x3FFF
    if ba_pa != 0x824C8000 or ba_pa + 0x4000 > p.phys + p.mem_size:
        raise ValueError("Stage57 boot_args address changed")
    return {"payload_sha256": digest, "entry_c_pa": hex(EXPECTED_ENTRY_C_PA),
            "join_pa": hex(EXPECTED_JOIN_PA), "ramdisk_pa": hex(rd_pa),
            "boot_args_pa": hex(ba_pa), "init_sha256": EXPECTED_INIT_SHA256}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE57 XNU/ADT/RAMDISK GUARD PASS", inspect(args.payload.read_bytes()))
