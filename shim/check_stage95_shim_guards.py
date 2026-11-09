#!/usr/bin/env python3
"""Fail the Stage95 build if any native shim guard differs from CI XNU bytes.

Checks both the original SHA-pinned Mach-O and the relocated boot payload.
The C source guard selection must be an explicit Stage95 branch above Stage91.
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from check_stage21b_mmu import Payload
from check_stage94_xnu import STAGE94_CHANGED
import mkpayload

KERNEL_SHA = "66d7e63cfd396c2cb16738418d10e6878875a395af0ef6f716fed882b42b4ff8"
STAGE95 = r"#if defined\(CACTUS_STAGE95_NATIVE\) && CACTUS_STAGE95_NATIVE"


def check(kernel_file: Path, payload_file: Path, c_file: Path) -> None:
    kernel = kernel_file.read_bytes()
    if hashlib.sha256(kernel).hexdigest() != KERNEL_SHA:
        raise ValueError("Stage95 XNU does not match the exact successful CI kernel")
    payload = Payload(payload_file.read_bytes(), expected_segments=11)
    macho = mkpayload.parse_macho(kernel)
    code = c_file.read_text(encoding="utf-8")
    branches = re.findall(STAGE95 + r"(.*?)#elif defined\(CACTUS_STAGE91_NATIVE\)", code, re.S)
    if len(branches) != 5:
        raise ValueError(f"Stage95 C shim guard/provenance branch count: {len(branches)} instead of 5")
    guard_target = STAGE94_CHANGED[0x81ac042c]
    if not ("#define STAGE20B_TARGET 0x81ac042cull" in branches[0]
            and f"#define STAGE20B_ORIG   {guard_target:#x}u" in branches[0]):
        raise ValueError("Stage95 branch target/original word is stale")
    if "loaded_boot_args_pa != 0x834c0000ull" not in branches[1]:
        raise ValueError("Stage95 boot-args location is stale")
    if "stage48_expected=" + f"{guard_target:#x}u" not in branches[3]:
        raise ValueError("Stage95 framebuffer guard word is stale")
    if "0x66d7e63cfd396c2cull" not in branches[4]:
        raise ValueError("Stage95 trace provenance marker is stale")
    for pa, expected in STAGE94_CHANGED.items():
        va = payload.virt + pa - payload.phys
        seg = next(s for s in macho["segs"] if s["vmaddr"] <= va < s["vmaddr"] + s["filesize"])
        from_kernel = struct.unpack_from("<I", kernel, seg["fileoff"] + va - seg["vmaddr"])[0]
        from_payload = payload.word(pa)
        if from_kernel != expected or from_payload != expected:
            raise ValueError(f"Opcode at {pa:#x}: CI={from_kernel:#x}, payload={from_payload:#x}, expected={expected:#x}")
        if not re.search(r"\{" + f"{pa:#x}" + r"ull," + f"{expected:#x}" + r"u\}", branches[2]):
            raise ValueError(f"Stage95 C shim pin at {pa:#x} mismatches kernel")
    print(f"STAGE95 SOURCE VERIFIED: {len(STAGE94_CHANGED)} checked instructions, 5 C guard branches, kernel {KERNEL_SHA}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--shim", type=Path, default=Path(__file__).with_name("stage19_probe.c"))
    args = parser.parse_args()
    check(args.kernel, args.payload, args.shim)
