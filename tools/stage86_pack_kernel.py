#!/usr/bin/env python3
"""Pack Stage86 using the Stage85 verified kernel and a real iOS HFS+ root."""

import argparse
import hashlib
from pathlib import Path

import stage27_pack_kernel as pack


KERNEL_SHA256 = "dd39a64cd43de54dd79a2eaabb23b3e689a242179baccdf6399c93aad1da13fc"
MAX_ROOT_BYTES = 32 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--root", type=Path, default=Path("_build/ios16-runtime/stage86-guestfs.hfs"))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    kernel = args.artifact_dir / "kernel.development.cactus"
    source = args.root if args.root.is_absolute() else project / args.root
    out = project / "shim/out/cactus/payload-stage86.bin"
    if not kernel.is_file() or hashlib.sha256(kernel.read_bytes()).hexdigest() != KERNEL_SHA256:
        raise SystemExit("Stage86 kernel does not match hardware-proven Stage85 source")
    sums = args.artifact_dir / "SHA256SUMS"
    if not sums.is_file() or not any(
        line.strip().startswith(KERNEL_SHA256) and line.split()[-1].lstrip("*") == kernel.name
        for line in sums.read_text().splitlines()
    ):
        raise SystemExit("Stage85 artifact SHA256SUMS mismatch")
    if not source.is_file() or not 1024 * 1024 < source.stat().st_size <= MAX_ROOT_BYTES:
        raise SystemExit("Stage86 HFS+ root missing or exceeds the allowed size")
    with source.open("rb") as handle:
        handle.seek(1024)
        if handle.read(2) != b"H+":
            raise SystemExit("Stage86 root must be a native HFS+ image")
    root_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if out.exists():
        raise SystemExit(f"Stage86 payload already exists; refusing overwrite: {out}")
    pack.STAGE77_VERIFIED_KERNEL_SHA256 = KERNEL_SHA256
    pack.STAGE65_VERIFIED_INIT_SHA256 = root_sha
    pack.prepare(kernel, project / "shim/out/cactus/payload.bin", out,
        stage61_live_fb=True, stage64_cactus_gic=True,
        stage65_cactus_pid1=True, stage66_topbar=True,
        stage67_vfs_probe=True, stage68_root_pid1=True,
        stage69_root_pid1=True, stage70_minimal_pid1=True,
        stage71_direct_pid1=True, stage72_mockfs_pid1=True,
        stage73_pid1_vm=True, stage74_physmap_pid1=True,
        stage75_exec_read=True, stage76_pid1_shadow=True,
        stage77_pid1_wired=True, ramdisk=source,
        extra_boot_args="unentitled_ios_sim_launch=1")
    print(f"STAGE86 ROOT SHA256={root_sha}")
    print(f"STAGE86 PACK PASS {out}")


if __name__ == "__main__":
    main()
