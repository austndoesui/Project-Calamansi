#!/usr/bin/env python3
"""Verify Stage28's null-PTE trap against the actual Stage27-built Mach-O."""
import argparse
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage27_entry import inspect as inspect_new_kernel
from check_stage25_pmap import PINS, TARGET_PA, TARGET_VA, ORIGINAL, PANIC_CALLEE


def inspect(data: bytes):
    inspect_new_kernel(data)
    p = Payload(data)
    for addr, opcode in PINS.items():
        actual = p.word(addr)
        if actual != opcode:
            raise ValueError(
                f"Stage28 rebuilt-XNU pmap drift {addr:#x}: "
                f"{actual:#x} != {opcode:#x}"
            )
    branch = ORIGINAL & 0x3ffffff
    if branch & (1 << 25):
        branch -= (1 << 26)
    if TARGET_PA + 4 * branch != PANIC_CALLEE:
        raise ValueError("Stage28 BRK replacement target no longer joins panic")
    if (p.virt + TARGET_PA - p.phys) & ((1 << 64) - 1) != TARGET_VA:
        raise ValueError("Stage28 pmap target virtual address drift")
    return TARGET_PA, TARGET_VA


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE28 REBUILT-XNU PMAP PANIC-JOIN GUARD PASS",
          inspect(args.payload.read_bytes()))
