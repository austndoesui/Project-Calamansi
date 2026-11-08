#!/usr/bin/env python3
"""Decode MediaTek arm64 mblock_info words printed by dtc in a DTS file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROPERTY = re.compile(r"\bmblock_info\s*=\s*<(?P<cells>.*?)>", re.DOTALL)
CELL = re.compile(r"0x([0-9a-fA-F]+)|(?<![\w.])([0-9]+)(?![\w.])")
MBLOCK_MAX = 128
RESERVED_MAX = 128
RESERVED_NAME_SIZE = 128


def words_from_dts(path: Path) -> list[int]:
    source = path.read_text(encoding="utf-8")
    match = PROPERTY.search(source)
    if not match:
        raise ValueError("no mblock_info property found")
    words = [int(a, 16) if a else int(b, 10) for a, b in CELL.findall(match["cells"])]
    if any(word > 0xFFFFFFFF for word in words):
        raise ValueError("mblock_info cells must be 32-bit values")
    return words


def le32(word: int) -> int:
    """Undo dtc's big-endian cell display of a little-endian struct word."""
    return int.from_bytes(word.to_bytes(4, "big"), "little")


def decode(words: list[int]) -> tuple[list[tuple[int, int, int]], list[tuple[str, int, int, int]]]:
    # arm64 layout: u32 count, 4-byte pad, 128 x {u64 start, u64 size, u32 rank, pad}.
    mblock_offset = 2
    mblock_words = 6
    count = le32(words[0])
    magic_index = mblock_offset + MBLOCK_MAX * mblock_words
    if count > MBLOCK_MAX or len(words) <= magic_index + 2:
        raise ValueError("mblock_info is shorter than the arm64 ABI header")
    if words[magic_index] != 0x99999999:
        raise ValueError(f"unexpected mblock magic 0x{words[magic_index]:08x}")
    version = le32(words[magic_index + 1])
    if version != 2:
        raise ValueError(f"unsupported mblock_info version {version}")

    def le64(index: int) -> int:
        return le32(words[index]) | (le32(words[index + 1]) << 32)

    mblocks = []
    for i in range(count):
        offset = mblock_offset + i * mblock_words
        mblocks.append((le64(offset), le64(offset + 2), le32(words[offset + 4])))

    # mblock_reserved is 152 bytes (38 cells); the containing array is
    # 8-byte aligned, so its first element starts at cell 774.
    reserved_count_index = magic_index + 2
    reserved_count = le32(words[reserved_count_index])
    if reserved_count > RESERVED_MAX:
        raise ValueError(f"reserved count {reserved_count} exceeds ABI maximum")
    reserved_base = reserved_count_index + 2
    reserved_bytes = 8 + 8 + 4 + RESERVED_NAME_SIZE
    reserved_words = ((reserved_bytes + 7) // 8 * 8) // 4
    if len(words) < reserved_base + reserved_count * reserved_words:
        raise ValueError("mblock_info is truncated in mblock_reserved entries")

    reserved = []
    for i in range(reserved_count):
        offset = reserved_base + i * reserved_words
        # The first array field is padded to an 8-byte boundary.
        if offset % 2:
            offset += 1
        start, size = le64(offset), le64(offset + 2)
        mapping = le32(words[offset + 4])
        name_offset = offset + 5
        raw_name = b"".join(
            words[j].to_bytes(4, "big")
            for j in range(name_offset, name_offset + RESERVED_NAME_SIZE // 4)
        )
        name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
        reserved.append((name, start, size, mapping))
    return mblocks, reserved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dts", type=Path, help="decompiled live FDT DTS file")
    args = parser.parse_args()
    try:
        mblocks, reserved = decode(words_from_dts(args.dts))
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))

    print("mblocks: # start end-exclusive size rank")
    for index, (start, size, rank) in enumerate(mblocks):
        print(f"{index} 0x{start:x} 0x{start + size:x} 0x{size:x} {rank}")
    print("reserved: name start end-exclusive size mapping")
    for name, start, size, mapping in reserved:
        print(f"{name} 0x{start:x} 0x{start + size:x} 0x{size:x} {mapping}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
