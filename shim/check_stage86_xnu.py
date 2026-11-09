#!/usr/bin/env python3
"""Check a Stage86 relocated XNU payload and its actual HFS+ root bytes."""

import argparse
import hashlib
import struct
import sys
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage85_xnu import C_ENTRY, EARLY, ENTRY, PINNED
from check_stage61_xnu import FB_PA, FB_STRIDE, FB_H

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import adt  # noqa: E402
import mkpayload  # noqa: E402


def validate(payload: Path, root_file: Path,
             expected_cmdline: bytes = b"debug=0xc rd=md0 unentitled_ios_sim_launch=1") -> dict:
    root = root_file.read_bytes()
    if len(root) != 16 * 1024 * 1024 or root[1024:1026] != b"H+":
        raise ValueError("Stage86 root must be the audited 16 MiB HFS+ volume")
    data = payload.read_bytes()
    p = Payload(data, expected_segments=11)
    if (p.entry, p.phys, p.mem_size, p.virt, p.segs[0][0]) != (
        ENTRY, 0x80000000, 0x1E000000, 0xFFFFFFF006000000, 0xFFFFFFF007004000
    ):
        raise ValueError("Stage86 native kernel entry/RAM layout differs from Stage85")
    for address, word in PINNED.items():
        if p.word(address) != word:
            raise ValueError(f"Stage85 native opcode changed at {address:#x}")
    for i, word in enumerate(EARLY):
        if p.word(0x8142E0EC + 4 * i) != word:
            raise ValueError(f"Stage85 early startup instruction changed: {i}")
    tree, end = adt.parse(data[p.adt_offset:p.adt_offset+p.adt_size])
    if end != p.adt_size:
        raise ValueError("ADT trailing bytes")
    framebuffer = next(n for n in tree.children if n.name == "sweet-fbcon")
    if struct.unpack("<2Q", framebuffer.prop("reg")) != (FB_PA, FB_H * FB_STRIDE):
        raise ValueError("Stage85 framebuffer changed")
    io = next(n for n in tree.children if n.name == "arm-io")
    gic = next(n for n in io.children if n.name == "gic")
    if gic.prop("reg") != struct.pack("<4Q", 0x0B000000, 0x40000, 0x0B100000, 0x200000):
        raise ValueError("Stage85 GIC mapping changed")
    chosen = next(n for n in tree.children if n.name == "chosen")
    mmap = next(n for n in chosen.children if n.name == "memory-map")
    pa, size = struct.unpack("<QQ", mmap.prop("RAMDisk"))
    segment = p.segs[-1]
    if (pa, size) != (p.phys + segment[0] - p.virt, segment[1]):
        raise ValueError("HFS+ RAMDisk does not match the relocated segment")
    if segment[3] != len(root) or data[segment[2]:segment[2]+segment[3]] != root:
        raise ValueError("Stage86 ramdisk is not the exact audited HFS+ image")
    if pa % 0x4000 or size % 0x4000:
        raise ValueError("RAMDisk alignment changed")
    cmd = data[mkpayload.CMDLINE:mkpayload.SEG_TABLE].split(b"\0", 1)[0]
    if cmd != expected_cmdline:
        raise ValueError("root-device kernel args changed")
    ba = (p.phys + p.kernel_end - p.virt + p.adt_size + 0x3FFF) & ~0x3FFF
    if pa + size > ba:
        raise ValueError("HFS RAMDisk overlaps kernel boot args")
    return {"entry": hex(p.entry), "root_pa": hex(pa), "root_bytes": segment[3],
            "root_sha256": hashlib.sha256(root).hexdigest(), "boot_args_pa": hex(ba),
            "opcode_pins": len(PINNED) + len(EARLY), "c_entry": hex(C_ENTRY)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print("STAGE86 VALIDATED:", validate(args.payload, args.root))
