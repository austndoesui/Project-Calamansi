#!/usr/bin/env python3
"""Strict Stage87 layout, root, native opcode, and GUI-handoff checks."""

import argparse
from pathlib import Path
from check_stage86_xnu import validate


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("payload", type=Path)
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    print("STAGE87 VALIDATED:", validate(
        args.payload, args.root,
        b"debug=0xc rd=md0 unentitled_ios_sim_launch=1 sweetfb_noconsole=1"))
