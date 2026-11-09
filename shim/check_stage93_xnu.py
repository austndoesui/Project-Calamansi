#!/usr/bin/env python3
"""Stage93 boot payload guard: inherit all Stage90/91 hardware pins.

Keep the exact handoff, RAM window, GIC, display, cmdline, and fallback HFS
requirements. Re-audit the five rebuilt-kernel instructions before flash.
"""
import argparse
from pathlib import Path

import check_stage90_xnu as base
from check_stage91_xnu import STAGE91_CHANGED


# Initially require unchanged Stage91 handoff words. If the new XNU build
# relocates instructions, replace only the confirmed values after inspecting
# the SHA-pinned CI Mach-O and the relocated Stage93 payload.
STAGE93_CHANGED = STAGE91_CHANGED.copy()


def validate(payload: Path, root: Path) -> dict:
    base.CHANGED = STAGE93_CHANGED
    result = base.validate(payload, root)
    result["stage"] = 93
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print("STAGE93 VALIDATED:", validate(args.payload, args.root))
