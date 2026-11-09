#!/usr/bin/env python3
"""Stage94 payload guard, retaining all verified Stage91 hardware pins."""
import argparse
from pathlib import Path

import check_stage93_xnu as stage93
import check_stage90_xnu as base


# Five source-verified instruction words from the SHA-pinned CI Mach-O
# 66d7e63cfd396c2cb16738418d10e6878875a395af0ef6f716fed882b42b4ff8.
# All other Stage85 early-boot pins still match unchanged.
STAGE94_CHANGED = {
    0x81abfdfc: 0x91012400,
    0x81abfe1c: 0x913a5400,
    0x81abfe24: 0xb0ffade2,
    0x81abfe2c: 0x97ff3c09,
    0x81ac042c: 0x913a5400,
}


def validate(payload: Path, root: Path) -> dict:
    base.CHANGED = STAGE94_CHANGED
    result = base.validate(payload, root)
    result["stage"] = 94
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print("STAGE94 VALIDATED:", validate(args.payload, args.root))
