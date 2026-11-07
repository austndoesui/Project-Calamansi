#!/usr/bin/env python3
"""Strict Stage85 XNU native profile for the Xcode 16 rebuilt cactus kernel."""
import argparse
import hashlib
import struct
from pathlib import Path
from check_stage21b_mmu import Payload
from check_stage61_xnu import FB_PA, FB_STRIDE, FB_W, FB_H
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import adt
import mkpayload

HASH = "3e7d17ebde20829bba1d272a5538c30f89c7eb1c2956884f7a91e156ca591a47"
INIT_HASH = "0d96929c37ea20608758e871fb102bca5be44135b39e459fa55e3064509f29b1"
ENTRY = 0xFFFFFFF00742C488
C_ENTRY = 0x81ABFDFC
PINNED = {
    0x8142c488: 0x14000719, 0x8142e0ec: 0xd510109f,
    0x8142e0f0: 0xd5034fdf, 0x8142e154: 0x90ffea79,
    0x8142e174: 0xd50041bf,
    0x8142e18c: 0xd50040bf, 0x8142e220: 0xd355ff05,
    0x8142e3d8: 0xd5182041, 0x8142e3e4: 0x940012f0,
    0x8142e3f4: 0xd5182020, 0x8142e43c: 0xd518a200,
    0x8142e494: 0xd5181000, 0x8142e498: 0xd5033fdf,
    0x81abfdfc: 0xd10343ff, 0x81abfe1c: 0xf0000a68,
    0x81abfe24: 0xf0ffade1, 0x81abfe2c: 0x52800020,
    0x81ac042c: 0xf9400108,
}
EARLY = (0xd510109f,0xd5034fdf,0xaa0003f4,0xd2800015,
         0xf2e00000,0xf2c00000,0xf2aff160,0xf2920000,
         0x12800001,0xd2800402,0xd2816804,0xd2800803,
         0xaa0003e5,0xb80044a1,0xf1000463,0x54ffffc1,
         0x8b040000,0xf1000442,0x54ffff21,0xd5033f9f,
         0xf0ffffe0,0x91000000,0xd518c000)

def inspect(data):
    if hashlib.sha256(data).hexdigest() != HASH:
        raise ValueError("Stage85 relocated XNU hash mismatch")
    p = Payload(data, expected_segments=11)
    if (p.entry,p.phys,p.mem_size,p.virt,p.segs[0][0]) != (
         ENTRY,0x80000000,0x1e000000,0xFFFFFFF006000000,0xFFFFFFF007004000):
        raise ValueError("Stage85 boot entry/memory layout differs")
    for pa,word in PINNED.items():
        if p.word(pa) != word: raise ValueError(f"Stage85 exact opcode mismatch {pa:#x}")
    for i,word in enumerate(EARLY):
        if p.word(0x8142e0ec+4*i) != word:
            raise ValueError(f"Stage85 bootstrap instruction mismatch #{i}")
    if p.word(0x8142c488) != 0x14000719 or p.word(0x8142e0ec) != 0xd510109f:
        raise ValueError("Stage85 XNU entry branch changed")
    if any(p.read(0x8117a000,0x4000)):
        raise ValueError("Stage85 native page-table scratch not zero")
    if p.qword(0x81178a18) != 0x22a5192519:
        raise ValueError("Stage85 TCR layout changed")
    if p.word(0x81004018) & 0x80000000:
        raise ValueError("Stage85 header relocation flag changed")
    root,end = adt.parse(data[p.adt_offset:p.adt_offset+p.adt_size])
    if end != p.adt_size: raise ValueError("Stage85 ADT has trailing bytes")
    fb = next(n for n in root.children if n.name == 'sweet-fbcon')
    if struct.unpack('<2Q',fb.prop('reg')) != (FB_PA, FB_H*FB_STRIDE):
        raise ValueError("Stage85 framebuffer mapping changed")
    io = next(n for n in root.children if n.name == 'arm-io')
    gic = next(n for n in io.children if n.name == 'gic')
    if gic.prop('reg') != struct.pack('<4Q',0x0b000000,0x40000,0x0b100000,0x200000):
        raise ValueError("Stage85 GIC physical MMIO changed")
    chosen = next(n for n in root.children if n.name == 'chosen')
    mmap = next(n for n in chosen.children if n.name == 'memory-map')
    rd_pa,rd_len = struct.unpack('<2Q',mmap.prop('RAMDisk'))
    rd=p.segs[-1]
    if (rd_pa,rd_len,p.phys+rd[0]-p.virt,rd[1],rd[3]) != (
            0x824b8000,0x8000,0x824b8000,0x8000,0x40fb):
        raise ValueError("Stage85 signed RAMDisk relocation changed")
    signed=data[rd[2]:rd[2]+rd[3]]
    if hashlib.sha256(signed).hexdigest()!=INIT_HASH:
        raise ValueError("Stage85 signed PID1 executable changed")
    cmd=data[mkpayload.CMDLINE:mkpayload.SEG_TABLE].split(b'\0',1)[0]
    if cmd != b'debug=0xc rd=md0':
        raise ValueError("Stage85 root-device command line changed")
    ba=(p.phys+p.kernel_end-p.virt+p.adt_size+0x3fff)&~0x3fff
    if ba!=0x824c4000:
        raise ValueError(f"Stage85 boot_args PA changed: {ba:#x}")
    return {'kernel_entry':hex(p.entry),'c_entry_pa':hex(C_ENTRY),
            'ramdisk_pa':hex(rd_pa),'boot_args_pa':hex(ba),
            'checked_opcodes':len(PINNED)+len(EARLY)}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('payload',type=Path);x=a.parse_args()
    print('STAGE85 VERIFIED:',inspect(x.payload.read_bytes()))
