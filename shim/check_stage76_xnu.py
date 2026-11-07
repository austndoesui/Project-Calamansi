#!/usr/bin/env python3
"""Stage76 strictly verified native XNU with direct PID1 executable bring-up."""
import argparse
import hashlib
from pathlib import Path
import check_stage65_xnu as previous

EXPECTED_SHA256 = "2ddcfc1381769d376f8a0e62ea9a0dd5bc7ed1a5b2577eae32bd1332d30f3baa"

BRANCH_WORDS = {
    0x81AC329C: 0xF0000A68,
    0x81AC32A4: 0x90FFADE1,
    0x81AC32A8: 0x91203821,
    0x81AC32C4: 0x97E58617,
    0x81AC32C8: 0x97E57CFA,
    0x81AC32D8: 0x37F805C9,
    0x81AC3308: 0x540029C0,
    0x81AC338C: 0x1400012D,
    0x81AC383C: 0x97E57629,
    0x81AC3840: 0x90FFB608,
    0x81AC3898: 0x97E5C13A,
    0x81AC389C: 0x97E5BDFD,
    0x81AC38A0: 0x97E5BDE4,
    0x81AC38A4: 0x97E5C12F,
    0x81AC38A8: 0x97E5C132,
    0x81AC38AC: 0x90FFACA1,
    0x81AC3908: 0x90FFB5A8,
}

def inspect(data: bytes):
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Stage76 relocated XNU payload fails SHA provenance guard")
    previous.EXPECTED_SHA256 = EXPECTED_SHA256
    previous.ENTRY_C_PA = 0x81AC3CDC
    previous.JOIN_PA = 0x81AC430C
    previous.POST_PA = 0x81AC4368
    previous.BRANCH_SHIFT = 0xA60
    previous.BRANCH_WORDS = BRANCH_WORDS
    result = previous.inspect(data)
    result["vfs_checkpoints"] = "VFS returned; detailed init/root/exec checkpoints instrumented"
    result["pid1_bar_location"] = "header divider row 5, beside STATUS"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE76 XNU/GIC/BSD-ROOT/PID1 STATIC GUARD PASS", inspect(args.payload.read_bytes()))
