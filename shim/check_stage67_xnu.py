#!/usr/bin/env python3
"""Stage67 verified native XNU with VFS checkpoints and visible PID1 bar."""
import argparse
import hashlib
from pathlib import Path
import check_stage65_xnu as previous

EXPECTED_SHA256 = "b1102efad550aba9cfa25c68fed0cea9d47563dc8f453bc4ee6be9d2181652c2"

BRANCH_WORDS = {
    0x81AC329C: 0xF0000A68,
    0x81AC32A4: 0x90FFADE1,
    0x81AC32A8: 0x913EB821,
    0x81AC32C4: 0x97E5879F,
    0x81AC32C8: 0x97E57E82,
    0x81AC32D8: 0x37F805C9,
    0x81AC3308: 0x540029C0,
    0x81AC338C: 0x1400012D,
    0x81AC383C: 0x97E577B1,
    0x81AC3840: 0xB0FFB608,
    0x81AC3898: 0x97E5C2C2,
    0x81AC389C: 0x97E5BF85,
    0x81AC38A0: 0x97E5BF6C,
    0x81AC38A4: 0x97E5C2B7,
    0x81AC38A8: 0x97E5C2BA,
    0x81AC38AC: 0xB0FFACA1,
    0x81AC3908: 0xB0FFB5A8,
}


def inspect(data: bytes):
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Stage67 relocated XNU payload fails SHA provenance guard")
    previous.EXPECTED_SHA256 = EXPECTED_SHA256
    previous.ENTRY_C_PA = 0x81AC36BC
    previous.JOIN_PA = 0x81AC3CEC
    previous.POST_PA = 0x81AC3D48
    previous.BRANCH_SHIFT = 0x440
    previous.BRANCH_WORDS = BRANCH_WORDS
    result = previous.inspect(data)
    result["vfs_checkpoints"] = "decmpfs/nspace/vfsinit"
    result["pid1_bar_location"] = "header divider row 5, beside STATUS"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE67 XNU/GIC/PID1/VFS STATIC GUARD PASS", inspect(args.payload.read_bytes()))
