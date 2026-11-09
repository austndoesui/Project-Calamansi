#!/usr/bin/env python3
"""Build-time Stage96 validator: pin compiled XNU instructions before the shim.

Extract expected words from the verified CI Mach-O, compare them with the
relocated payload, then emit a local C header for the native shim guards.
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import check_stage90_xnu as base
from check_stage21b_mmu import Payload
import mkpayload

PIN_ADDRESSES = (0x81abfdfc, 0x81abfe1c, 0x81abfe24, 0x81abfe2c, 0x81ac042c)


def verify(kernel_file: Path, sums_file: Path, payload_file: Path, root_file: Path,
           shim_source: Path, header_file: Path, stage: int = 96) -> None:
    kernel = kernel_file.read_bytes()
    kernel_sha = hashlib.sha256(kernel).hexdigest()
    listed = [line.split()[0] for line in sums_file.read_text().splitlines()
              if line.rstrip().endswith("kernel.development.cactus")]
    if len(listed) != 1 or listed[0] != kernel_sha:
        raise ValueError("Stage96 kernel does not match CI SHA256SUMS")

    if stage == 98:
        required = (
            b"CACTUS IOS16: shared-cache CS enforcement disabled by boot argument",
            b"CACTUS IOS16: launchd dyld cache map begin",
            b"CACTUS IOS16: launchd dyld cache map result=",
        )
        for marker in required:
            if marker not in kernel:
                raise ValueError(f"Stage98 compiled kernel missing {marker!r}")

    p = Payload(payload_file.read_bytes(), expected_segments=11)
    macho = mkpayload.parse_macho(kernel)
    words = {}
    for pa in PIN_ADDRESSES:
        va = p.virt + pa - p.phys
        seg = next((seg for seg in macho["segs"]
                    if seg["vmaddr"] <= va < seg["vmaddr"] + seg["filesize"]), None)
        if seg is None:
            raise ValueError(f"pinned instruction {pa:#x} missing in CI Mach-O")
        ci_word = struct.unpack_from("<I", kernel, seg["fileoff"] + va - seg["vmaddr"])[0]
        relocated_word = p.word(pa)
        if ci_word != relocated_word:
            raise ValueError(f"pin {pa:#x} CI={ci_word:#x} payload={relocated_word:#x}")
        words[pa] = ci_word

    # Apply all 41 existing native ADT/FB/GIC/eMMC/early instruction guards.
    base.CHANGED = words
    if stage == 98:
        # Full literal bootargs validation still applies, including this new
        # explicit opt-in. Stage96's original pinned arguments stay unchanged.
        base.CMD = base.CMD + b" cs_enforcement_disable=1 cs_debug=1"
    result = base.validate(payload_file, root_file)

    c_source = shim_source.read_text(encoding="utf-8")
    blocks = re.findall(
        r"#if defined\(CACTUS_STAGE96_NATIVE\) && CACTUS_STAGE96_NATIVE"
        r"(.*?)#elif defined\(CACTUS_STAGE95_NATIVE\)",
        c_source, re.S)
    if len(blocks) != 5:
        raise ValueError(f"Stage96 source guard branches: expected 5, got {len(blocks)}")
    if not all(f"CACTUS96_WORD_{pa:08X}" in c_source for pa in PIN_ADDRESSES):
        raise ValueError("Stage96 C guard does not use generated pin definitions")
    if "CACTUS96_KERNEL_PREFIX" not in blocks[4]:
        raise ValueError("Stage96 trace provenance is not pinned")

    header = [
        "/* Generated from SHA-verified CI XNU; do not edit. */",
        "#ifndef CACTUS_STAGE96_PINS_H",
        "#define CACTUS_STAGE96_PINS_H",
        f"/* kernel.development.cactus SHA256: {kernel_sha} */",
        f"#define CACTUS96_KERNEL_PREFIX 0x{kernel_sha[:16]}ull",
    ]
    header.extend(f"#define CACTUS96_WORD_{pa:08X} 0x{word:08x}u"
                  for pa, word in words.items())
    header.append("#endif")
    header_file.parent.mkdir(parents=True, exist_ok=True)
    header_file.write_text("\n".join(header) + "\n", encoding="utf-8")
    print(f"STAGE96 SOURCE/PAYLOAD VERIFIED SHA={kernel_sha} pins={len(words)} "
          f"total_guards={result['opcode_pins']} header={header_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--sums", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shim", type=Path, default=Path(__file__).with_name("stage19_probe.c"))
    parser.add_argument("--header", type=Path, default=Path(__file__).parent / "out/cactus/stage96-pins.h")
    parser.add_argument("--stage", type=int, choices=(96, 98), default=96)
    args = parser.parse_args()
    verify(args.kernel, args.sums, args.payload, args.root, args.shim, args.header, args.stage)
