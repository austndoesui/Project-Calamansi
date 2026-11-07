#!/usr/bin/env python3
"""Fail-closed Stage65: real cactus GIC ADT, native XNU, and PID1 proof."""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

import check_stage61_xnu as baseline
from check_stage21b_mmu import Payload

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import adt

EXPECTED_SHA256 = "741af2fc4f5ae3302a76f10243e79ef91cb6e9cbf9916ec79cd7eeae764bb08b"
EXPECTED_INIT_SHA256 = "f0b8d9f4e5d841691efe23b1521e756b743665484be82b9e7082c71626e7fe5d"

# Verified against the relocated Stage65 binary from GH Actions 41586007450.
# The native entry and MMU pins are unchanged; early C moved +0x220 from
# Stage63, with compiler-relocated branch immediates audited individually.
BRANCH_WORDS = {
    0x81AC329C: 0xF0000A68,
    0x81AC32A4: 0xB0FFADE1,
    0x81AC32A8: 0x9100B821,
    0x81AC32C4: 0x97E58803,
    0x81AC32C8: 0x97E57EE6,
    0x81AC32D8: 0x37F805C9,
    0x81AC3308: 0x540029C0,
    0x81AC338C: 0x1400012D,
    0x81AC383C: 0x97E57815,
    0x81AC3840: 0xB0FFB608,
    0x81AC3898: 0x97E5C326,
    0x81AC389C: 0x97E5BFE9,
    0x81AC38A0: 0x97E5BFD0,
    0x81AC38A4: 0x97E5C31B,
    0x81AC38A8: 0x97E5C31E,
    0x81AC38AC: 0xB0FFACA1,
    0x81AC3908: 0xB0FFB5A8,
}
ENTRY_C_PA = 0x81AC352C
JOIN_PA = 0x81AC3B5C
POST_PA = 0x81AC3BB8
BRANCH_SHIFT = 0x2B0


def inspect(data: bytes) -> dict:
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Stage65 payload differs from independently audited artifact")
    baseline.EXPECTED_SHA256 = EXPECTED_SHA256
    baseline.EXPECTED_INIT_SHA256 = EXPECTED_INIT_SHA256
    baseline.EXPECTED_ENTRY_C_PA = ENTRY_C_PA
    baseline.EXPECTED_JOIN_PA = JOIN_PA
    baseline.EXPECTED_POST_PA = POST_PA
    baseline.EXPECTED_C_BRANCH_PINS = {
        pa + BRANCH_SHIFT: word for pa, word in BRANCH_WORDS.items()
    }
    result = baseline.inspect(data)
    payload = Payload(data, expected_segments=11)
    root, end = adt.parse(data[payload.adt_offset:payload.adt_offset + payload.adt_size])
    if end != payload.adt_size:
        raise ValueError("Stage65 ADT trailing bytes")
    io = next((n for n in root.children if n.name == "arm-io"), None)
    if io is None or io.prop("ranges") != struct.pack("<3Q", 0, 0x01000000, 0xFF000000):
        raise ValueError("Stage65 SoC base is not cactus")
    gic = next((n for n in io.children if n.name == "gic"), None)
    if gic is None or gic.prop("reg") != struct.pack(
        "<4Q", 0x0B000000, 0x40000, 0x0B100000, 0x200000
    ):
        raise ValueError("Stage65 GIC MMIO addresses differ from physical census")
    result.update({"gicd_phys": hex(0x0C000000), "gicr_phys": hex(0x0C100000),
                   "pid1_marker": "getpid(1) syscall only"})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE65 XNU/GIC/PID1 STATIC GUARD PASS", inspect(args.payload.read_bytes()))
