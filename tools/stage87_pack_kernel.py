#!/usr/bin/env python3
"""Stage87: audited iOS HFS+ root and automatic GUI console handoff.

Use the exact Stage85 XNU kernel, preserving its native entry/provenance.
The platform and graphics boot arguments enable already-built kernel paths.
"""

import argparse
import hashlib
from pathlib import Path

import stage27_pack_kernel as pack
from stage86_pack_kernel import KERNEL_SHA256, MAX_ROOT_BYTES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("artifact_dir", type=Path)
    p.add_argument("--root", type=Path,
                   default=Path("_build/ios16-runtime/stage87-guestfs.hfs"))
    args = p.parse_args()
    project = Path(__file__).resolve().parents[1]
    kernel = args.artifact_dir / "kernel.development.cactus"
    root = args.root if args.root.is_absolute() else project / args.root
    out = project / "shim/out/cactus/payload-stage87.bin"
    if not kernel.is_file() or hashlib.sha256(kernel.read_bytes()).hexdigest() != KERNEL_SHA256:
        raise SystemExit("Stage87 requires exact hardware-proven Stage85 kernel")
    sums = args.artifact_dir / "SHA256SUMS"
    if not sums.is_file() or not any(
        row.strip().startswith(KERNEL_SHA256) and
        row.split()[-1].lstrip("*") == kernel.name
        for row in sums.read_text().splitlines()
    ):
        raise SystemExit("Stage85 SHA256SUMS provenance mismatch")
    if not root.is_file() or not 1024 * 1024 < root.stat().st_size <= MAX_ROOT_BYTES:
        raise SystemExit("Stage87 HFS+ root missing or invalid size")
    with root.open("rb") as fp:
        fp.seek(1024)
        if fp.read(2) != b"H+":
            raise SystemExit("Stage87 root must be native HFS+")
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing Stage87 payload: {out}")
    root_sha = hashlib.sha256(root.read_bytes()).hexdigest()
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
                 stage77_pid1_wired=True, ramdisk=root,
                 extra_boot_args="unentitled_ios_sim_launch=1 sweetfb_noconsole=1")
    print(f"STAGE87 ROOT SHA256={root_sha}")
    print(f"STAGE87 PACK PASS {out}")


if __name__ == "__main__":
    main()
