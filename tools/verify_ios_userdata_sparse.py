#!/usr/bin/env python3
"""Bit-for-bit verify the 16GiB iOS HFS+ root against its Android sparse image.

Checks the whole decoded sparse stream without expanding it into another
16GiB temporary file. The verified sparse may then be used with fastboot's
userdata partition only after checking the connected device's partition size.
"""
import argparse
import os
import struct
from pathlib import Path

SPARSE_HEADER = struct.Struct("<IHHHHIIII")
CHUNK_HEADER = struct.Struct("<HHII")
SPARSE_MAGIC = 0xED26FF3A
RAW, FILL, DONT_CARE, CRC32 = 0xCAC1, 0xCAC2, 0xCAC3, 0xCAC4
BUF = 4 * 1024 * 1024


def verify(source: Path, sparse: Path, partition_bytes: int) -> None:
    with source.open("rb") as raw, sparse.open("rb") as src:
        h = src.read(SPARSE_HEADER.size)
        if len(h) != SPARSE_HEADER.size:
            raise ValueError("truncated sparse header")
        magic, major, minor, file_header, chunk_header, blocksize, blocks, count, checksum = SPARSE_HEADER.unpack(h)
        if (magic != SPARSE_MAGIC or major != 1 or minor != 0 or
                file_header < SPARSE_HEADER.size or chunk_header < CHUNK_HEADER.size or
                blocksize != 4096 or source.stat().st_size != blocks * blocksize or
                blocks * blocksize > partition_bytes):
            raise ValueError("sparse header, root extent or partition size mismatch")
        src.seek(file_header)
        decoded = 0
        raw_chunks = 0
        fill_chunks = 0
        skipped_chunks = 0
        for index in range(count):
            header = src.read(chunk_header)
            if len(header) != chunk_header:
                raise ValueError(f"chunk {index}: truncated header")
            kind, reserved, chunk_blocks, chunk_bytes = CHUNK_HEADER.unpack_from(header)
            if reserved != 0 or chunk_blocks > blocks - decoded // blocksize:
                raise ValueError(f"chunk {index}: invalid count/reserved field")
            bytes_needed = chunk_blocks * blocksize
            if kind == RAW:
                if chunk_bytes != chunk_header + bytes_needed:
                    raise ValueError(f"chunk {index}: raw length mismatch")
                raw_chunks += 1
                remaining = bytes_needed
                while remaining:
                    n = min(remaining, BUF)
                    if src.read(n) != raw.read(n):
                        raise ValueError(f"chunk {index}: RAW data does not match HFS image")
                    remaining -= n
            elif kind in (FILL, DONT_CARE):
                expected_total = chunk_header + (4 if kind == FILL else 0)
                if chunk_bytes != expected_total:
                    raise ValueError(f"chunk {index}: invalid fill/hole length")
                if kind == FILL:
                    pattern = src.read(4)
                    if len(pattern) != 4:
                        raise ValueError(f"chunk {index}: truncated fill")
                    fill_chunks += 1
                else:
                    pattern = b"\x00" * 4
                    skipped_chunks += 1
                remaining = bytes_needed
                while remaining:
                    n = min(remaining, BUF)
                    if raw.read(n) != pattern * (n // 4):
                        raise ValueError(f"chunk {index}: fill/hole mismatch with HFS image")
                    remaining -= n
            elif kind == CRC32:
                if chunk_blocks != 0 or chunk_bytes != chunk_header + 4 or len(src.read(4)) != 4:
                    raise ValueError(f"chunk {index}: invalid CRC chunk")
            else:
                raise ValueError(f"chunk {index}: unknown type {kind:#x}")
            decoded += bytes_needed
        if decoded != blocks * blocksize or raw.read(1) or src.read(1):
            raise ValueError("trailing bytes or incorrect decoded length")
        print("IOS_USERDATA_SPARSE_VERIFIED", {
            "logical_bytes": decoded, "partition_bytes": partition_bytes,
            "chunks": count, "raw": raw_chunks, "fill": fill_chunks,
            "zero": skipped_chunks, "sparse_bytes": os.stat(sparse).st_size,
            "image": str(sparse),
        })


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("raw_hfs", type=Path)
    p.add_argument("sparse_image", type=Path)
    p.add_argument("--partition-bytes", type=lambda x: int(x, 0), required=True)
    a = p.parse_args()
    verify(a.raw_hfs, a.sparse_image, a.partition_bytes)
