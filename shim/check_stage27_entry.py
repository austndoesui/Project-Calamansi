#!/usr/bin/env python3
"""Pin the newly compiled Stage27 Cactus XNU entry and continuation code.

This guard is intentionally separate from Stage22: the rebuilt Mach-O
changes two C-code instructions but retains the proven early MMU path.
Do not update either profile silently if the kernel is rebuilt again.
"""
import argparse
import struct
from pathlib import Path

from check_stage21b_mmu import Payload, audit
from check_stage21c2_entry import inspect as inspect_c2
from check_stage21d_entry import (
    ENTRY, EL1H_VECTOR, EL1H_ORIGINAL, PROLOGUE,
)
from check_stage22_entry import PINS, TARGET, TARGET_VA

KERNEL_ENTRY = 0x8142D488
KERNEL_ENTRY_VA = 0xFFFFFFF00742D488
NEW_PROLOGUE_WORD_11 = 0x913CF021
NEW_CALL = 0x97E59383
CHANGED_PROLOGUE_PA = ENTRY + 11 * 4
CHANGED_CALL_PA = 0x81AC0624


def inspect(data: bytes):
    inspect_c2(data)
    p = Payload(data)
    mmu = audit(data)
    expected = list(PROLOGUE)
    expected[11] = NEW_PROLOGUE_WORD_11
    if tuple(struct.unpack("<16I", p.read(ENTRY, 64))) != tuple(expected):
        raise ValueError("Stage27 high-VA C entry prologue changed")
    if tuple(struct.unpack("<4I", p.read(EL1H_VECTOR, 16))) != EL1H_ORIGINAL:
        raise ValueError("Stage27 EL1h synchronous exception vector changed")
    revised = dict(PINS)
    revised[CHANGED_CALL_PA] = NEW_CALL
    for address, word in revised.items():
        actual = p.word(address)
        if actual != word:
            raise ValueError(
                f"Stage27 continuation drift at {address:#x}: "
                f"{actual:#x} != {word:#x}"
            )
    if (p.entry, p.virt + KERNEL_ENTRY - p.phys) != (
        KERNEL_ENTRY_VA, KERNEL_ENTRY_VA
    ):
        raise ValueError("new kernel entry or physical relocation drifted")
    if (p.virt + TARGET - p.phys) & ((1 << 64)-1) != TARGET_VA:
        raise ValueError("new checkpoint high VA drifted")
    if mmu["post_mmu_return_va"] != 0xFFFFFFF007AC05DC:
        raise ValueError("post-MMU branch target changed")
    if not mmu["bootstrap_ram_map"][0] <= TARGET < mmu["bootstrap_ram_map"][1]:
        raise ValueError("continuation checkpoint is outside initial mappings")
    # The same conditional/unconditional join is preserved.
    if (0x81AC0668 + (((revised[0x81AC0668] >> 5) & 0x7ffff) << 2)
            != 0x81AC0BA0
            or 0x81AC06EC + ((revised[0x81AC06EC] & 0x3ffffff) << 2)
            != 0x81AC0BA0):
        raise ValueError("Stage27 C entry join moved")
    return p.entry, TARGET_VA


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    entry, checkpoint = inspect(args.payload.read_bytes())
    print(f"STAGE27 C-AARCH64 ENTRY GUARD PASS "
          f"entry={entry:#x} checkpoint={checkpoint:#x}")
