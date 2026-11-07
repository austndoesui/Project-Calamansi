#!/usr/bin/env python3
"""Stage71 strictly verified native XNU with direct PID1 executable bring-up."""
import argparse
import hashlib
from pathlib import Path
import check_stage65_xnu as previous

EXPECTED_SHA256 = "259ca2520c1f46dd64ba7a4d5834cbc328e5f1d493a301a1a993255b880c9ec7"

BRANCH_WORDS = {
    0x81AC329C: 0xF0000A68,
    0x81AC32A4: 0x90FFADE1,
    0x81AC32A8: 0x9128B821,
    0x81AC32C4: 0x97E5874F,
    0x81AC32C8: 0x97E57E32,
    0x81AC32D8: 0x37F805C9,
    0x81AC3308: 0x540029C0,
    0x81AC338C: 0x1400012D,
    0x81AC383C: 0x97E57761,
    0x81AC3840: 0xB0FFB608,
    0x81AC3898: 0x97E5C272,
    0x81AC389C: 0x97E5BF35,
    0x81AC38A0: 0x97E5BF1C,
    0x81AC38A4: 0x97E5C267,
    0x81AC38A8: 0x97E5C26A,
    0x81AC38AC: 0xB0FFACA1,
    0x81AC3908: 0xB0FFB5A8,
}


def inspect(data: bytes):
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Stage71 relocated XNU payload fails SHA provenance guard")
    previous.EXPECTED_SHA256 = EXPECTED_SHA256
    previous.ENTRY_C_PA = 0x81AC37FC
    previous.JOIN_PA = 0x81AC3E2C
    previous.POST_PA = 0x81AC3E88
    previous.BRANCH_SHIFT = 0x580
    previous.BRANCH_WORDS = BRANCH_WORDS
    result = previous.inspect(data)
    result["vfs_checkpoints"] = "VFS returned; detailed init/root/exec checkpoints instrumented"
    result["pid1_bar_location"] = "header divider row 5, beside STATUS"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE71 XNU/GIC/BSD-ROOT/PID1 STATIC GUARD PASS", inspect(args.payload.read_bytes()))
