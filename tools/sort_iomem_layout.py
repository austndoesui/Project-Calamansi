#!/usr/bin/env python3
"""Group iomem ranges by their resource name, then sort ranges in each group."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


RANGE_LINE = re.compile(
    r"^\s*(?P<start>[0-9a-fA-F]+)-(?P<end>[0-9a-fA-F]+)\s*:\s*(?P<name>.+?)\s*$"
)


def group_iomem(text: str) -> str:
    groups: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        match = RANGE_LINE.match(line)
        if not match:
            raise ValueError(f"line {line_number}: expected 'start-end : name'")

        start = int(match.group("start"), 16)
        end = int(match.group("end"), 16)
        if end < start:
            raise ValueError(
                f"line {line_number}: end address 0x{end:x} is before start 0x{start:x}"
            )
        groups[match.group("name")].append((start, end))

    sections: list[str] = []
    for name in sorted(groups, key=str.casefold):
        sections.append(f"{name}:")
        for start, end in sorted(groups[name]):
            sections.append(f"  {start:08x}-{end:08x}")
        sections.append("")

    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Group iomem ranges by name and sort addresses within each name."
    )
    parser.add_argument("input", type=Path, help="input text file (use - for stdin)")
    parser.add_argument(
        "-o", "--output", type=Path, help="write output here instead of stdout"
    )
    args = parser.parse_args()

    try:
        source = sys.stdin.read() if str(args.input) == "-" else args.input.read_text()
        result = group_iomem(source)
        if args.output:
            args.output.write_text(result)
        else:
            sys.stdout.write(result)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
