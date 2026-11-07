#!/usr/bin/env python3
"""Build Stage55 diagnostic PID 1 with GNU ARM64 tools; no Apple SDK needed.

The Cactus assembly is strictly position independent. Reject relocations,
unexpected architecture and nonzero entrypoint before wrapping the raw text
in the existing ad-hoc signed Mach-O code (mkinit.build_code).
"""
import argparse
import hashlib
import re
import struct
import subprocess
from pathlib import Path

import mkinit


def run(*argv: str) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout


def build(source: Path, out_dir: Path, tool_prefix: str = "aarch64-linux-gnu-") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    obj = out_dir / "cactus-init.o"
    text = out_dir / "cactus-init.text"
    macho = out_dir / "cactus-init.macho"
    run(tool_prefix + "gcc", "-c", "-x", "assembler-with-cpp", "-nostdlib",
        str(source), "-o", str(obj))
    header = run(tool_prefix + "readelf", "-h", str(obj))
    if "Machine:                           AArch64" not in header or "Type:                              REL" not in header:
        raise ValueError("unexpected ELF input architecture/type")
    relocation_report = run(tool_prefix + "readelf", "-rW", str(obj))
    if "There are no relocations in this file." not in relocation_report:
        raise ValueError("diagnostic init has unresolved relocations")
    symbols = run(tool_prefix + "nm", "--defined-only", str(obj))
    entries = re.findall(r"^([0-9A-Fa-f]+)\s+[Tt]\s+_start$", symbols, re.M)
    if entries != ["0000000000000000"]:
        raise ValueError(f"diagnostic init missing zero-offset _start: {entries}")
    run(tool_prefix + "objcopy", "--only-section=.text", "-O", "binary",
        str(obj), str(text))
    code = text.read_bytes()
    binary = mkinit.build_code(code, 0)
    if struct.unpack_from("<II", binary) != (0xFEEDFACF, 0x0100000C):
        raise ValueError("generated Mach-O is not arm64")
    macho.write_bytes(binary)
    digest = hashlib.sha256(binary).hexdigest()
    (out_dir / "cactus-init.macho.sha256").write_text(
        f"{digest}  cactus-init.macho\n", encoding="ascii")
    print("CACTUS_STATIC_PID1_BUILT", macho, "text", len(code),
          "macho", len(binary), "sha256", digest)
    return macho


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,
                    default=Path(__file__).with_name("cactus-init.S"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefix", default="aarch64-linux-gnu-")
    args = ap.parse_args()
    build(args.source, args.out, args.prefix)
