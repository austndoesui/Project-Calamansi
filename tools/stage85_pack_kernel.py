#!/usr/bin/env python3
"""Package an Actions-built cactus Stage85 kernel without changing Stage78."""
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
        raise SystemExit("Stage85 kernel and Actions SHA256SUMS required")
    expected = next(
        (line.split()[0] for line in sums.read_text().splitlines()
         if line.split() and line.split()[-1].lstrip("*") == kernel.name),
        None,
    )
    if not expected:
        raise SystemExit("Stage85 Actions SHA256SUMS lacks kernel entry")
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
        b"ST82 PID1 exec read returned",
        b"ST82 PID1 activator",
        b"PID1 load_machfile done",
        b"ST83 PID1 executable pagein enter",
        b"ST84 PID1 MachO caller success",
        b"ST84 PID1 zone check enter",
        b"ST84 PID1 thread state ready",
        b"ST84 PID1 task switch enter",
        b"ST85 PID1 stack prefault enter",
        b"ST85 PID1 map switch enter",
        b"ST85 PID1 string copy enter",
        b"ST85 EL",
    ):
        if data.count(marker) != 1:
            raise SystemExit(f"Stage85 provenance marker incorrect: {marker!r}")
    pack.STAGE77_VERIFIED_KERNEL_SHA256 = expected
    # Stage85's init performs getpid as its first syscall. Pin the newly
    # audited binary here without changing historical Stage65 verification.
    init_binary = root / "shim/out/cactus/stage65-init/cactus-init.macho"
    new_init_sha = "0d96929c37ea20608758e871fb102bca5be44135b39e459fa55e3064509f29b1"
    if hashlib.sha256(init_binary.read_bytes()).hexdigest() != new_init_sha:
        raise SystemExit("Stage85 getpid-first init SHA256 mismatch")
    pack.STAGE65_VERIFIED_INIT_SHA256 = new_init_sha
    out = root / "shim/out/cactus/payload-stage85.bin"
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
    print("STAGE85 PACK PASS", observed, out)

if __name__ == "__main__":
    main()
