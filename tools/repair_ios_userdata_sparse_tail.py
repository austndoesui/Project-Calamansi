#!/usr/bin/env python3
"""Create a minimal sparse repair for the already-written iOS userdata image.

The stock MTK fastboot failed on the final sparse chunk, which includes almost
10 GiB of zero-fill chunks. Preserve the existing successful writes and
reapply the final 256 MiB of iOS data plus its backup HFS+ header. All other
logical blocks use Android sparse DONT_CARE, which leaves them untouched.
"""
import argparse
import struct
from pathlib import Path

HEADER = struct.Struct("<IHHHHIIII")
CHUNK = struct.Struct("<HHII")
RAW, FILL, SKIP = 0xCAC1, 0xCAC2, 0xCAC3
TAIL_BYTES = 256 * 1024 * 1024


def build(source: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"refusing overwrite {target}")
    with source.open("rb") as src:
        h = src.read(HEADER.size)
        magic, major, minor, hdr_bytes, ch_bytes, blocksize, blocks, count, _ = HEADER.unpack(h)
        if (magic, major, minor, hdr_bytes, ch_bytes, blocksize) != (
            0xED26FF3A, 1, 0, 28, 12, 4096
        ):
            raise ValueError("unexpected source sparse format")
        src.seek(hdr_bytes)
        parts = []
        current_block = 0
        for index in range(count):
            kind, reserved, nblocks, total = CHUNK.unpack(src.read(CHUNK.size))
            if kind not in (RAW, FILL) or reserved != 0:
                raise ValueError(f"unsupported source chunk #{index}: {kind:#x}")
            where = src.tell()
            beg = current_block * blocksize
            end = (current_block + nblocks) * blocksize
            parts.append((kind, nblocks, beg, end, where, total - CHUNK.size))
            src.seek(total - CHUNK.size, 1)
            current_block += nblocks
        if current_block != blocks or blocks * blocksize != 16 * 1024 ** 3:
            raise ValueError("source sparse does not describe exact 16 GiB")
        main_raw = [i for i, p in enumerate(parts) if p[0] == RAW and p[3] < 16 * 1024 ** 3]
        if not main_raw:
            raise ValueError("source has no main HFS data")
        last_main = main_raw[-1]
        cutoff = parts[last_main][3] - TAIL_BYTES
        # The iPhone X root has substantially more allocated HFS data than
        # the older iPhone 8 donor. Keep the tail relative to the last actual
        # data chunk, with an explicit backup-header guard at the volume end.
        if not (0 < cutoff < 16 * 1024 ** 3 - TAIL_BYTES):
            raise ValueError("unexpected HFS data location")
        backup = parts[-1]
        if (backup[0] != RAW or backup[2] != 16 * 1024 ** 3 - 4096
                or backup[3] != 16 * 1024 ** 3 or backup[5] != 4096):
            raise ValueError("missing final 4 KiB backup HFS header")

        selected = []
        for i, (kind, nblocks, beg, end, where, amount) in enumerate(parts):
            keep = i == len(parts)-1 or (end > cutoff and i <= last_main)
            selected.append(keep)

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb+") as out:
            out.write(b"\x00" * HEADER.size)
            new_chunks = 0
            selected_bytes = 0
            pending_skip = 0

            def flush_skip() -> None:
                nonlocal pending_skip, new_chunks
                if pending_skip:
                    out.write(CHUNK.pack(SKIP, 0, pending_skip, CHUNK.size))
                    pending_skip = 0
                    new_chunks += 1

            for (kind, nblocks, beg, end, where, amount), keep in zip(parts, selected):
                if not keep:
                    pending_skip += nblocks
                    continue
                flush_skip()
                out.write(CHUNK.pack(kind, 0, nblocks, CHUNK.size + amount))
                src.seek(where)
                remaining = amount
                while remaining:
                    data = src.read(min(remaining, 4 * 1024 * 1024))
                    if not data:
                        raise ValueError("truncated source sparse data")
                    out.write(data)
                    remaining -= len(data)
                new_chunks += 1
                selected_bytes += amount
            flush_skip()
            out.seek(0)
            out.write(HEADER.pack(0xED26FF3A, 1, 0, 28, 12, 4096, blocks,
                                  new_chunks, 0))

    print("IOS_USERDATA_TAIL_REPAIR", {
        "source": str(source), "output": str(target),
        "raw_tail_cutoff": hex(cutoff),
        "last_nonbackup_data_end": hex(parts[last_main][3]),
        "selected_payload_bytes": selected_bytes,
        "new_chunks": new_chunks, "size": target.stat().st_size,
        "logical_size": blocks * blocksize,
    })


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("source", type=Path)
    args.add_argument("target", type=Path)
    a = args.parse_args()
    build(a.source, a.target)
