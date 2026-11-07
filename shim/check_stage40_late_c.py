#!/usr/bin/env python3
"""Guard the exact Stage40 XNU early-C checkpoint in the rebuilt kernel."""
import argparse
from pathlib import Path

from check_stage21b_mmu import Payload
from check_stage28_pmap import inspect as inspect_stage28

TARGET_PA = 0x81AC0C20
TARGET_VA = 0xFFFFFFF007AC0C20
ORIGINAL = 0x97FE7424  # BL first early-C boot-argument lookup
CHECKPOINTS = {
    40: (TARGET_PA, TARGET_VA, ORIGINAL),
    41: (0x81A5DCB0, 0xFFFFFFF007A5DCB0, 0xD10303FF),
    42: (0x81AC0C24, 0xFFFFFFF007AC0C24, 0x7100041F),
    43: (0x81AC0C64, 0xFFFFFFF007AC0C64, 0x97DFAB47),
    44: (0x81AC0C68, 0xFFFFFFF007AC0C68, 0x90FFB5C8),
}
LEADING_WORDS = {
    0x81AC0C0C: 0xB0FFACC1,  # Stage36 confirmed C join
    0x81AC0C10: 0x912A4821,
    0x81AC0C14: 0x9100E3E2,
    0x81AC0C18: 0xAA1F03E0,
    0x81AC0C1C: 0xF90027FF,
    TARGET_PA: ORIGINAL,
    TARGET_PA + 4: 0x7100041F,
    TARGET_PA + 8: 0x54002B61,
    0x81AC0C40: 0x97FE7690,  # second boot-argument parse
    0x81AC0C60: 0x52800020,  # the second call's branch join
    0x81AC0C64: 0x97DFAB47,  # next platform initialization call
    0x81AC0C68: 0x90FFB5C8,
}


def inspect(data: bytes, stage: int = 40):
    inspect_stage28(data)
    payload = Payload(data)
    target_pa, target_va, expected = CHECKPOINTS[stage]
    if payload.word(target_pa) != expected:
        raise ValueError(
            f"Stage{stage} XNU checkpoint drift at {target_pa:#x}: "
            f"got {payload.word(target_pa):#x}, expected {expected:#x}"
        )
    for address, expected in LEADING_WORDS.items():
        actual = payload.word(address)
        if actual != expected:
            raise ValueError(
                f"Stage40 XNU startup drift at {address:#x}: "
                f"got {actual:#x}, expected {expected:#x}"
            )
    if (payload.virt + TARGET_PA - payload.phys) & ((1 << 64) - 1) != TARGET_VA:
        raise ValueError("Stage40 checkpoint high virtual address changed")
    displacement = ORIGINAL & 0x3FFFFFF
    if displacement & (1 << 25):
        displacement -= 1 << 26
    callee = TARGET_VA + 4 * displacement
    if callee != 0xFFFFFFF007A5DCB0:
        raise ValueError(f"Stage40 branch destination changed: {callee:#x}")
    later = LEADING_WORDS[0x81AC0C64] & 0x3FFFFFF
    if later & (1 << 25):
        later -= 1 << 26
    if (0xFFFFFFF007AC0C64 + later * 4) != 0xFFFFFFF0072AB980:
        raise ValueError("Stage43 platform initialization call target changed")
    if (payload.virt + target_pa - payload.phys) & ((1 << 64) - 1) != target_va:
        raise ValueError(f"Stage{stage} checkpoint high virtual address changed")
    return target_pa, target_va


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--stage", type=int, choices=tuple(CHECKPOINTS), default=40)
    args = parser.parse_args()
    pa, va = inspect(args.payload.read_bytes(), args.stage)
    print(f"STAGE{args.stage} XNU LATE-C GUARD PASS pa={pa:#x} va={va:#x}")
