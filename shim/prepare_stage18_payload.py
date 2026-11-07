#!/usr/bin/env python3
"""Create a *copy* of the existing SWEETXNU payload with coherent cactus ADT
RAM bounds for read-only Stage18 validation. Never modify the source payload.

The 480 MiB window [0x80000000,0x9e000000) is an initial admission
candidate inside the 510 MiB gap seen in Stage17. It is NOT a verified
functional XNU VM layout; XNU may require a different memory strategy.
"""
from pathlib import Path
import argparse
import struct
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import adt  # noqa: E402

CANDIDATE_BASE = 0x80000000
CANDIDATE_SIZE = 0x1e000000


def change(source: Path, target: Path):
    if source.resolve() == target.resolve():
        raise ValueError("source payload must never be modified in place")
    raw = bytearray(source.read_bytes())
    if len(raw) < 0x2a8 or raw[:8] != b"SWEETXNU":
        raise ValueError("not a SWEETXNU payload")
    version, segments = struct.unpack_from("<II", raw, 8)
    virt, entry, off, size, kend, old_base, old_size = struct.unpack_from(
        "<7Q", raw, 0x10)
    if version != 1 or not 1 <= segments <= 64:
        raise ValueError("unsupported version/segment count")
    if old_base != 0x70000000 or old_size != 0x50000000:
        raise ValueError("input must be the original cactus RAM layout")
    if off > len(raw) or size > len(raw) - off:
        raise ValueError("ADT outside the source payload")
    root, _ = adt.parse(bytes(raw[off:off + size]))
    chosen = next(c for c in root.children if c.name == "chosen")
    props = {name: i for i, (name, _flags, _data) in enumerate(chosen.props)}
    for key, value, original in (
        ("dram-base", CANDIDATE_BASE, old_base),
        ("dram-size", CANDIDATE_SIZE, old_size),
    ):
        if key not in props:
            raise ValueError("ADT missing " + key)
        index = props[key]
        name, flags, data = chosen.props[index]
        if len(data) != 8 or struct.unpack("<Q", data)[0] != original:
            raise ValueError("ADT source RAM and payload header disagree")
        chosen.props[index] = (name, flags, struct.pack("<Q", value))
    # A packed in-memory root is a segment at the original physical base.
    # The Stage18 handoff moves every segment into candidate RAM, so the
    # /chosen/memory-map RAMDisk pointer must move by the same delta.
    mmap = next((n for n in chosen.children if n.name == "memory-map"), None)
    if mmap is not None and mmap.prop("RAMDisk") is not None:
        rd = mmap.prop("RAMDisk")
        if len(rd) != 16:
            raise ValueError("invalid memory-map/RAMDisk descriptor")
        rd_pa, rd_size = struct.unpack("<QQ", rd)
        segs = [struct.unpack_from("<4Q", raw, 0x2a8 + i * 32)
                for i in range(segments)]
        matching = [s for s in segs
                    if old_base + s[0] - virt == rd_pa and s[1] == rd_size]
        if len(matching) != 1 or rd_pa < old_base or rd_pa + rd_size > old_base + old_size:
            raise ValueError("RAMDisk ADT pointer does not identify one packed segment")
        if rd_size % 0x4000 or rd_pa % 0x4000:
            raise ValueError("RAMDisk must be aligned to XNU's 16KiB granule")
        for i, (name, flags, value) in enumerate(mmap.props):
            if name == "RAMDisk":
                mmap.props[i] = (name, flags,
                                 struct.pack("<QQ", rd_pa + CANDIDATE_BASE - old_base,
                                             rd_size))
                break
    modified = adt.serialize(root)
    if len(modified) != size:
        raise ValueError("ADT changed size unexpectedly")
    raw[off:off + size] = modified
    struct.pack_into("<2Q", raw, 0x38, CANDIDATE_BASE, CANDIDATE_SIZE)
    if kend < virt or kend - virt + size + 0x8000 > CANDIDATE_SIZE:
        raise ValueError("candidate cannot contain segments, ADT and boot_args")
    recheck, _ = adt.parse(bytes(raw[off:off + size]))
    values = {k: struct.unpack("<Q", v)[0] for c in recheck.children
              if c.name == "chosen" for k, f, v in c.props
              if k in ("dram-base", "dram-size")}
    if values != {"dram-base": CANDIDATE_BASE,
                  "dram-size": CANDIDATE_SIZE}:
        raise ValueError("ADT relocation failed verification")
    if mmap is not None and mmap.prop("RAMDisk") is not None:
        chosen_new = next(c for c in recheck.children if c.name == "chosen")
        mmap_new = next(c for c in chosen_new.children if c.name == "memory-map")
        new_rd = struct.unpack("<QQ", mmap_new.prop("RAMDisk"))
        if new_rd != (rd_pa + CANDIDATE_BASE - old_base, rd_size):
            raise ValueError("RAMDisk physical pointer relocation failed verification")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    print(f"Stage18 read-only payload copy: {target} ({len(raw)} bytes)")
    print(f"physical window: {CANDIDATE_BASE:#x}.."
          f"{CANDIDATE_BASE+CANDIDATE_SIZE:#x} (480 MiB)")
    print(f"entry VA: {entry:#x}, kernel footprint {kend-virt:#x}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    change(args.source, args.output)
