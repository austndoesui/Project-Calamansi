#!/usr/bin/env python3
"""Verify Stage89 CI kernel provenance, early entry opcodes, HFS and bootargs."""
import argparse
import hashlib
import struct
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage85_xnu import PINNED, EARLY
from check_stage61_xnu import FB_PA, FB_STRIDE, FB_H
from check_stage86_xnu import adt, mkpayload


PAYLOAD_SOURCE_SHA = "171cda0ae0d9b4b67cc35f38d9205431c0c2079296f8c06fc41870027d2bc4f8"
ROOT_SHA = "cf281dccb5b69add3ef01070a3ed21202287727dffa982772fd705ff4acaeea9"
CMD = b"debug=0xc rd=md0 unentitled_ios_sim_launch=1 sweetfb_noconsole=1 cactus_emmc_probe=1"
# These five C-entry instructions changed in the exact successful CI run.
CHANGED = {
    0x81abfdfc: 0x97ff3a65,
    0x81abfe1c: 0x5280006b,
    0x81abfe24: 0xb0ffade8,
    0x81abfe2c: 0x92403c09,
    0x81ac042c: 0x97ff38d9,
}


def validate(payload: Path, root_file: Path) -> dict:
    root = root_file.read_bytes()
    if len(root) != 16 * 1024 * 1024 or root[1024:1026] != b"H+":
        raise ValueError("Stage89 must retain the 16MiB Stage87 HFS+ root")
    if hashlib.sha256(root).hexdigest() != ROOT_SHA:
        raise ValueError("Stage89 root content differs from audited Stage87")
    data = payload.read_bytes()
    p = Payload(data, expected_segments=11)
    if (p.entry, p.phys, p.mem_size, p.virt, p.segs[0][0], p.kernel_end) != (
        0xfffffff00742c488, 0x80000000, 0x1e000000,
        0xfffffff006000000, 0xfffffff007004000, 0xfffffff0094bc000
    ):
        raise ValueError("Stage89 new XNU entry/RAM/footprint differs from audited CI kernel")
    pins = PINNED.copy()
    pins.update(CHANGED)
    for address, word in pins.items():
        if p.word(address) != word:
            raise ValueError(f"Stage89 native opcode mismatch at {address:#x}")
    for i, word in enumerate(EARLY):
        if p.word(0x8142e0ec + i * 4) != word:
            raise ValueError(f"Stage89 early startup mismatch at instruction #{i}")
    tree, end = adt.parse(data[p.adt_offset:p.adt_offset + p.adt_size])
    if end != p.adt_size:
        raise ValueError("ADT has trailing bytes")
    framebuffer = next(n for n in tree.children if n.name == "sweet-fbcon")
    if struct.unpack("<2Q", framebuffer.prop("reg")) != (FB_PA, FB_H * FB_STRIDE):
        raise ValueError("Stage89 framebuffer changed")
    io = next(n for n in tree.children if n.name == "arm-io")
    gic = next(n for n in io.children if n.name == "gic")
    if gic.prop("reg") != struct.pack("<4Q", 0x0b000000, 0x40000,
                                       0x0b100000, 0x200000):
        raise ValueError("Stage89 GIC mapping changed")
    chosen = next(n for n in tree.children if n.name == "chosen")
    mmap = next(n for n in chosen.children if n.name == "memory-map")
    pa, size = struct.unpack("<QQ", mmap.prop("RAMDisk"))
    segment = p.segs[-1]
    if (pa, size) != (p.phys + segment[0] - p.virt, segment[1]):
        raise ValueError("Stage89 HFS+ ramdisk physical mapping changed")
    if segment[3] != len(root) or data[segment[2]:segment[2] + segment[3]] != root:
        raise ValueError("Stage89 HFS image bytes not exact")
    cmdline = data[mkpayload.CMDLINE:mkpayload.SEG_TABLE].split(b"\0", 1)[0]
    if cmdline != CMD:
        raise ValueError(f"Stage89 bootargs changed: {cmdline!r}")
    ba = (p.phys + p.kernel_end - p.virt + p.adt_size + 0x3fff) & ~0x3fff
    if pa + size > ba:
        raise ValueError("Stage89 ramdisk overlaps kernel boot arguments")
    return {"entry": hex(p.entry), "root_pa": hex(pa),
            "root_sha256": ROOT_SHA, "boot_args_pa": hex(ba),
            "opcode_pins": len(pins) + len(EARLY),
            "kernel_end": hex(p.kernel_end)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print("STAGE89 VALIDATED:", validate(args.payload, args.root))
