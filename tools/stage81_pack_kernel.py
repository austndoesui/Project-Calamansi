#!/usr/bin/env python3
"""Package an Actions-built cactus Stage81 kernel without changing Stage78."""
import argparse
import hashlib
from pathlib import Path
import stage27_pack_kernel as pack

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact_dir", type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    kernel = args.artifact_dir / "kernel.development.cactus"
    sums = args.artifact_dir / "SHA256SUMS"
    if not kernel.is_file() or not sums.is_file():
        raise SystemExit("Stage81 kernel and Actions SHA256SUMS required")
    expected = next(
        (line.split()[0] for line in sums.read_text().splitlines()
         if line.split() and line.split()[-1].lstrip("*") == kernel.name),
        None,
    )
    if not expected:
        raise SystemExit("Stage81 Actions SHA256SUMS lacks kernel entry")
    data = kernel.read_bytes()
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected:
        raise SystemExit(f"kernel artifact mismatch {observed} != {expected}")
    for marker in (
        b"ST79 mockfs devread enter",
        b"ST79 mockfs devread finished",
        b"ST78 hdr err=",
        b"ST80 PID1 MachO header valid",
        b"ST80 PID1 MachO loader entered",
        b"waiting for XNU",
        b"ST81 PID1 VNOP_READ returned",
        b"ST81 PID1 vn_rdwr returning",
    ):
        if data.count(marker) != 1:
            raise SystemExit(f"Stage81 provenance marker incorrect: {marker!r}")
    pack.STAGE77_VERIFIED_KERNEL_SHA256 = expected
    out = root / "shim/out/cactus/payload-stage81.bin"
    pack.prepare(kernel, root / "shim/out/cactus/payload.bin", out,
        stage61_live_fb=True, stage64_cactus_gic=True,
        stage65_cactus_pid1=True, stage66_topbar=True,
        stage67_vfs_probe=True, stage68_root_pid1=True,
        stage69_root_pid1=True, stage70_minimal_pid1=True,
        stage71_direct_pid1=True, stage72_mockfs_pid1=True,
        stage73_pid1_vm=True, stage74_physmap_pid1=True,
        stage75_exec_read=True, stage76_pid1_shadow=True,
        stage77_pid1_wired=True,
        ramdisk=root / "shim/out/cactus/stage65-init/cactus-init.macho")
    print("STAGE81 PACK PASS", observed, out)

if __name__ == "__main__":
    main()
