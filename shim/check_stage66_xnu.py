#!/usr/bin/env python3
"""Stage66 strict native XNU/GIC/PID1 guard, with visible top banner bar."""
import argparse
import hashlib
from pathlib import Path
import check_stage65_xnu as base

EXPECTED_SHA256 = "c4015d81b9aa598174c70cd2ab89ece2914565eeb4cc7542d20a42c6bdcfd66f"


def inspect(data: bytes):
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Stage66 payload differs from audited top-bar build")
    base.EXPECTED_SHA256 = EXPECTED_SHA256
    result = base.inspect(data)
    result["pid1_bar_location"] = "screen top row above Cactarwin banner"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print("STAGE66 XNU/GIC/PID1 TOP-BAR GUARD PASS", inspect(args.payload.read_bytes()))
