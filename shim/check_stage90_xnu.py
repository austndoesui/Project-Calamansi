#!/usr/bin/env python3
"""Stage90 verifier: check exact CI opcode pins, root selection and relocation."""
import argparse
import hashlib
import struct
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage85_xnu import EARLY, PINNED
from check_stage61_xnu import FB_PA, FB_H, FB_STRIDE
from check_stage86_xnu import adt, mkpayload

ROOT_SHA = "cf281dccb5b69add3ef01070a3ed21202287727dffa982772fd705ff4acaeea9"
CMD = (
    b"debug=0xc rd=emmcroot0 cactusroot=userdata cactusrw=1 rootrw=1 "
    b"unentitled_ios_sim_launch=1 ignition_level=1 "
    b"launchd_unsecure_cache=1 sweetfb_noconsole=1 "
    b"wdt_test=no_user_checkin wdt=-1"
)
CHANGED = {
    0x81abfdfc: 0x97ff3b65,
    0x81abfe1c: 0x97ff3b5d,
    0x81abfe24: 0x910003fd,
    0x81abfe2c: 0x9107dc00,
    0x81ac042c: 0x9107dc00,
}


def validate(payload: Path, root_file: Path) -> dict:
    root = root_file.read_bytes()
    if (len(root) != 16 * 1024 * 1024 or root[1024:1026] != b"H+" or
            hashlib.sha256(root).hexdigest() != ROOT_SHA):
        raise ValueError("Stage90 RAMDisk fallback root failed SHA/HFS check")
    data = payload.read_bytes()
    p = Payload(data, expected_segments=11)
    if (p.entry, p.phys, p.mem_size, p.virt, p.segs[0][0], p.kernel_end) != (
        0xfffffff00742c488, 0x80000000, 0x1e000000,
        0xfffffff006000000, 0xfffffff007004000, 0xfffffff0094bc000
    ):
        raise ValueError("Stage90 native XNU entry/RAM/layout changed")
    pins = PINNED.copy()
    pins.update(CHANGED)
    for addr, word in pins.items():
        if p.word(addr) != word:
            raise ValueError(f"Stage90 guard pin differs at {addr:#x}")
    for index, word in enumerate(EARLY):
        addr = 0x8142e0ec + 4 * index
        if p.word(addr) != word:
            raise ValueError(f"Stage90 early boot pin differs at {addr:#x}")
    tree, end = adt.parse(data[p.adt_offset:p.adt_offset + p.adt_size])
    if end != p.adt_size:
        raise ValueError("unparsed ADT data")
    fb = next(n for n in tree.children if n.name == "sweet-fbcon")
    if struct.unpack("<2Q", fb.prop("reg")) != (FB_PA, FB_H * FB_STRIDE):
        raise ValueError("framebuffer mapping changed")
    io = next(n for n in tree.children if n.name == "arm-io")
    gic = next(n for n in io.children if n.name == "gic")
    if gic.prop("reg") != struct.pack("<4Q", 0x0b000000, 0x40000, 0x0b100000, 0x200000):
        raise ValueError("GIC mapping changed")
    chosen = next(n for n in tree.children if n.name == "chosen")
    memmap = next(n for n in chosen.children if n.name == "memory-map")
    pa, size = struct.unpack("<QQ", memmap.prop("RAMDisk"))
    segment = p.segs[-1]
    if (pa, size) != (p.phys + segment[0] - p.virt, segment[1]):
        raise ValueError("Stage90 fallback root physical pointer incorrect")
    if segment[3] != len(root) or data[segment[2]:segment[2] + segment[3]] != root:
        raise ValueError("Stage90 fallback root bytes incorrect")
    cmdline = data[mkpayload.CMDLINE:mkpayload.SEG_TABLE].split(b"\0", 1)[0]
    if cmdline != CMD:
        raise ValueError(f"Stage90 native userdata root arguments incorrect: {cmdline!r}")
    boot_args_pa = (p.phys + p.kernel_end - p.virt + p.adt_size + 0x3fff) & ~0x3fff
    if pa + size > boot_args_pa:
        raise ValueError("RAMDisk overlaps boot arguments")
    return {"entry": hex(p.entry), "boot_args_pa": hex(boot_args_pa),
            "root_device": "emmcroot0", "opcode_pins": len(pins) + len(EARLY),
            "fallback_root_sha256": ROOT_SHA, "native_root_write": "userdata"}


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("payload", type=Path)
    args.add_argument("--root", type=Path, required=True)
    a = args.parse_args()
    print("STAGE90 VALIDATED:", validate(a.payload, a.root))
