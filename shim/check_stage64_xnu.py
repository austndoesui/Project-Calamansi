#!/usr/bin/env python3
"""Stage64: pin Stage63 native XNU and validate corrected cactus GIC ADT."""
import argparse
import hashlib
import struct
from pathlib import Path

import check_stage63_xnu as stage63
from check_stage21b_mmu import Payload
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import adt

EXPECTED_SHA256 = '51d6cd4877bce3036c411ff4b6adc37afaf21ea34699b9554ea270c053714072'


def inspect(data: bytes):
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Stage64 relocated payload differs from audited GIC fix')
    # Validate every Stage63 native entry, MMU, branch, framebuffer, RAMDisk
    # and PID1 pin in addition to this new ADT-specific regression guard.
    stage63.EXPECTED_SHA256 = EXPECTED_SHA256
    result = stage63.inspect(data)
    payload = Payload(data, expected_segments=11)
    root, end = adt.parse(data[payload.adt_offset:payload.adt_offset + payload.adt_size])
    if end != payload.adt_size:
        raise ValueError('Stage64 ADT has invalid length')
    io = next((node for node in root.children if node.name == 'arm-io'), None)
    if io is None or io.prop('ranges') != struct.pack('<3Q', 0, 0x01000000, 0xff000000):
        raise ValueError('Stage64 SoC physical base differs from verified cactus')
    gic = next((node for node in io.children if node.name == 'gic'), None)
    expected = struct.pack('<4Q', 0x0b000000, 0x40000, 0x0b100000, 0x200000)
    if gic is None or gic.prop('reg') != expected:
        raise ValueError('Stage64 GIC points outside real cactus MMIO regions')
    result['gicd_phys'] = '0x0c000000'
    result['gicr_phys'] = '0x0c100000'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('payload', type=Path)
    args = parser.parse_args()
    print('STAGE64 VERIFIED GIC ADT/XNU/RAMDISK PASS', inspect(args.payload.read_bytes()))
