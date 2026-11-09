#!/usr/bin/env python3
"""Exact Stage91 XNU pin profile; retains all Stage90 root/ADT/FB guards."""
import argparse
from pathlib import Path

import check_stage90_xnu as base

# Filled only after comparing the downloaded CI Mach-O against the relocated
# Stage91 payload. Never assume the Stage90 instructions survived a rebuild.
STAGE91_CHANGED = {
    0x81abfdfc: 0x913e0d29,
    0x81abfe1c: 0x913e0c00,
    0x81abfe24: 0x90ffade2,
    0x81abfe2c: 0x97ff3b99,
    0x81ac042c: 0x913e0d29,
}


def validate(payload: Path, root: Path) -> dict:
    base.CHANGED = STAGE91_CHANGED
    return base.validate(payload, root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print("STAGE91 VALIDATED:", validate(args.payload, args.root))
