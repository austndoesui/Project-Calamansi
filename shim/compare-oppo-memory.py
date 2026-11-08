#!/usr/bin/env python3
"""Compare Stage 15 level-5 fixed FDT reservations with Linux System RAM."""
import argparse
import importlib.machinery
from pathlib import Path
import re


def load_decoder():
    path = Path(__file__).with_name("decode-cactus-usb.py")
    return importlib.machinery.SourceFileLoader("cactus_usb_decode", str(path)).load_module()


def load_mblock_decoder():
    path = Path(__file__).resolve().parents[1] / "tools" / "decode_mblock_info.py"
    return importlib.machinery.SourceFileLoader("decode_mblock_info", str(path)).load_module()


def parse_system_ram(path):
    pattern = re.compile(r"^\s*([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+:\s+System RAM\s*$")
    result = []
    for line in path.read_text(errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            start, inclusive_end = (int(value, 16) for value in match.groups())
            if inclusive_end < start:
                raise ValueError(f"invalid System RAM interval: {line}")
            result.append((start, inclusive_end + 1))
    if not result:
        raise ValueError(f"no System RAM intervals found in {path}")
    return result


def parse_debugfs_memblock_reserved(path):
    # debugfs prints inclusive endpoints as "N: 0xSTART..0xEND".
    pattern = re.compile(
        r"^\s*\d+:\s*(0x[0-9a-fA-F]+)\.\.(0x[0-9a-fA-F]+)\s*$"
    )
    result = []
    for line in path.read_text(errors="replace").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        start, inclusive_end = (int(value, 16) for value in match.groups())
        if inclusive_end < start:
            raise ValueError(f"invalid memblock reserved interval: {line}")
        result.append((start, inclusive_end + 1))
    if not result:
        raise ValueError(f"no memblock reserved intervals found in {path}")
    return result


def merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def subtract(start, end, reserved):
    pieces = [(start, end)]
    for rstart, rend in reserved:
        next_pieces = []
        for pstart, pend in pieces:
            if rend <= pstart or rstart >= pend:
                next_pieces.append((pstart, pend))
            else:
                if pstart < rstart:
                    next_pieces.append((pstart, rstart))
                if rend < pend:
                    next_pieces.append((rend, pend))
        pieces = next_pieces
    return pieces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iomem", type=Path, help="saved /proc/iomem text")
    parser.add_argument("capture", type=Path, help="raw Stage 15 level-5 CLOG capture")
    parser.add_argument(
        "--live-dts", type=Path,
        help="decompiled live FDT DTS containing memory/mblock_info "
             "(defaults to oppo_lfdt.dts beside iomem)",
    )
    parser.add_argument(
        "--debugfs-reserved", type=Path,
        help="same-boot /sys/kernel/debug/memblock/reserved capture",
    )
    args = parser.parse_args()

    live_dts = args.live_dts or args.iomem.with_name("oppo_lfdt.dts")
    if not live_dts.is_file():
        raise SystemExit(
            f"missing live FDT DTS with mblock_info: {live_dts}; "
            "pass it with --live-dts"
        )
    mblock_decoder = load_mblock_decoder()
    try:
        _, mblock_reserved = mblock_decoder.decode(
            mblock_decoder.words_from_dts(live_dts)
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"could not decode mblock_info from {live_dts}: {exc}")
    boot_reserved = [
        (start, start + size)
        for _name, start, size, _mapping in mblock_reserved
        if size > 0
    ]
    runtime_reserved = []
    if args.debugfs_reserved:
        try:
            runtime_reserved = parse_debugfs_memblock_reserved(args.debugfs_reserved)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"could not parse {args.debugfs_reserved}: {exc}")

    decoder = load_decoder()
    records, corrupt, noise = decoder.decode(args.capture.read_bytes())
    stage_records = [r for r in records if r["stage"] == 15]
    summaries = [r for r in stage_records if r["event"] == 0x158b]
    ranges = [r for r in stage_records if r["event"] == 0x158c]
    if len(summaries) != 1:
        raise SystemExit(f"expected one FDT reservation summary, found {len(summaries)}")
    entries = [r for r in stage_records if r["event"] == 0x1580]
    fdt_checks = [r for r in stage_records if r["event"] == 0x1588]
    if len(entries) != 1 or len(fdt_checks) != 1:
        raise SystemExit("expected one Stage 15 entry and FDT check record")

    summary = summaries[0]
    dtb_start = entries[0]["a"]
    dtb_size = fdt_checks[0]["b"]
    if not dtb_size or dtb_start + dtb_size > (1 << 64):
        raise SystemExit(f"invalid live DTB interval: base={dtb_start:#x} size={dtb_size:#x}")
    expected = summary["a"]
    indexed = {r["a"]: (r["b"], r["c"]) for r in ranges}
    if len(indexed) != len(ranges) or set(indexed) != set(range(expected)):
        raise SystemExit(f"reservation records incomplete: expected {expected}, got {len(indexed)}")
    reserved = []
    for index in range(expected):
        base, size = indexed[index]
        if not size or base + size > (1 << 64):
            raise SystemExit(f"invalid FDT reservation #{index}: base={base:#x} size={size:#x}")
        reserved.append((base, base + size))
    reserved = merge(reserved)
    initrd_start, initrd_end = summary["b"], summary["c"]
    if initrd_end < initrd_start:
        raise SystemExit(f"invalid initrd interval: [{initrd_start:#x},{initrd_end:#x})")
    exclusions = list(reserved)
    exclusions.extend(boot_reserved)
    exclusions.extend(runtime_reserved)
    if initrd_end > initrd_start:
        exclusions.append((initrd_start, initrd_end))
    exclusions.append((dtb_start, dtb_start + dtb_size))
    exclusions = merge(exclusions)
    banks = parse_system_ram(args.iomem)

    print(f"capture_frames={len(records)} bad_frames={corrupt} unmatched_bytes={noise}")
    print(f"FDT fixed reservation entries={expected}; initrd=[{summary['b']:#x},{summary['c']:#x})")
    print(f"Live DTB=[{dtb_start:#x},{dtb_start + dtb_size:#x}) size={dtb_size:#x}")
    print(f"Bootloader mblock_info reservations={len(mblock_reserved)} from {live_dts}")
    print("Bootloader reservations (merged):")
    for start, end in merge(boot_reserved):
        print(f"  [{start:#010x}, {end:#010x}) size={end-start:#x}")
    print("Fixed FDT reservations (merged):")
    for start, end in reserved:
        print(f"  [{start:#010x}, {end:#010x}) size={end-start:#x}")
    if args.debugfs_reserved:
        print(f"Android runtime memblock reserved entries={len(runtime_reserved)} from {args.debugfs_reserved}")
        for start, end in merge(runtime_reserved):
            print(f"  [{start:#010x}, {end:#010x}) size={end-start:#x}")
    print("System RAM after subtracting FDT/mblock reservations, initrd, live DTB,")
    if args.debugfs_reserved:
        print("and captured Android runtime memblock reservations:")
    else:
        print("and captured Android runtime memblock reservations (not supplied):")
    for start, end in banks:
        print(f"  bank [{start:#010x}, {end:#010x})")
        for left, right in subtract(start, end, exclusions):
            print(f"    candidate [{left:#010x}, {right:#010x}) size={right-left:#x}")
    print("Caveat: remaining spans are still not approved XNU allocator ranges.")
    print("Android runtime memblock reservations may include Linux-specific allocations;")
    print("dynamic reserved-memory nodes and platform ownership still need classification.")


if __name__ == "__main__":
    main()
