#!/usr/bin/env python3
"""Pinned Stage63 XNU, ADT and signed RAMDisk static admission guard.

Stage63 retains the audited native bootstrap and payload layout of Stage61.
The new native GIC logging shifts the early C routine by 0x90 bytes and
changes several branch immediates. These addresses and words were read
directly from the freshly relocated Stage63 Mach-O, not inferred from stage
numbers. A successful guard does not establish native execution.
"""
import argparse
from pathlib import Path

import check_stage61_xnu as baseline


EXPECTED_SHA256 = "f7100f3d9f5f17fb4b1dcdad47b8ba13d06037901416566334e2362ef8c9c747"
EARLY_C_SHIFT = 0x90
BRANCH_WORDS = {
    0x81AC329C: 0xF0000A68,
    0x81AC32A4: 0xB0FFADE1,
    0x81AC32A8: 0x91023821,
    0x81AC32C4: 0x97E5888B,
    0x81AC32C8: 0x97E57F6E,
    0x81AC32D8: 0x37F805C9,
    0x81AC3308: 0x540029C0,
    0x81AC338C: 0x1400012D,
    0x81AC383C: 0x97E5789D,
    0x81AC3840: 0xB0FFB608,
    0x81AC3898: 0x97E5C3AE,
    0x81AC389C: 0x97E5C071,
    0x81AC38A0: 0x97E5C058,
    0x81AC38A4: 0x97E5C3A3,
    0x81AC38A8: 0x97E5C3A6,
    0x81AC38AC: 0xB0FFACA1,
    0x81AC3908: 0xB0FFB5A8,
}


def inspect(data: bytes) -> dict:
    # All Stage61 checks (native entry, MMU instructions, vector table,
    # payload geometry, FB ADT, RAMDisk pointer, signed init and cmdline)
    # still apply. Re-pin only the verified Stage63 C addresses/opcodes.
    baseline.EXPECTED_SHA256 = EXPECTED_SHA256
    baseline.EXPECTED_ENTRY_C_PA = 0x81AC330C
    baseline.EXPECTED_JOIN_PA = 0x81AC393C
    baseline.EXPECTED_POST_PA = 0x81AC3998
    baseline.EXPECTED_C_BRANCH_PINS = {
        pa + EARLY_C_SHIFT: word for pa, word in BRANCH_WORDS.items()
    }
    return baseline.inspect(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE63 XNU/ADT/RAMDISK GUARD PASS", inspect(args.payload.read_bytes()))
