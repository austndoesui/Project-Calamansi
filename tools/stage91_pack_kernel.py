#!/usr/bin/env python3
"""Pack the SHA-pinned Stage91 native iOS userdata root kernel."""
import hashlib
from pathlib import Path

import stage27_pack_kernel as pack
from stage90_pack_kernel import EXTRA_BOOT_ARGS, ROOT_SHA256

KERNEL_SHA256 = "b22e157d0eedc2344cd3ddf1d98afb5c23df46855f215eada70536334387a4ba"
CI_RUN = "42479641169"


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    artifacts = project / "_build/_xnu-ci-worktree/_artifacts/run5"
    kernel = artifacts / "kernel.development.cactus"
    root = project / "_build/ios16-runtime/stage87-guestfs.hfs"
    output = project / "shim/out/cactus/payload-stage91.bin"
    if output.exists():
        raise SystemExit(f"refusing to overwrite: {output}")
    if hashlib.sha256(kernel.read_bytes()).hexdigest() != KERNEL_SHA256:
        raise SystemExit("Stage91 CI kernel checksum differs")
    if f"{KERNEL_SHA256}  {kernel.name}" not in (artifacts / "SHA256SUMS").read_text():
        raise SystemExit("Stage91 CI SHA256SUMS differs")
    if root.stat().st_size != 16 * 1024 * 1024 or hashlib.sha256(root.read_bytes()).hexdigest() != ROOT_SHA256:
        raise SystemExit("Stage91 known-good diagnostic HFS root differs")
    pack.STAGE77_VERIFIED_KERNEL_SHA256 = KERNEL_SHA256
    pack.STAGE65_VERIFIED_INIT_SHA256 = ROOT_SHA256
    pack.prepare(
        kernel, project / "shim/out/cactus/payload.bin", output,
        stage61_live_fb=True, stage64_cactus_gic=True,
        stage65_cactus_pid1=True, stage66_topbar=True,
        stage67_vfs_probe=True, stage68_root_pid1=True,
        stage69_root_pid1=True, stage70_minimal_pid1=True,
        stage71_direct_pid1=True, stage72_mockfs_pid1=True,
        stage73_pid1_vm=True, stage74_physmap_pid1=True,
        stage75_exec_read=True, stage76_pid1_shadow=True,
        stage77_pid1_wired=True, ramdisk=root,
        root_device="emmcroot0", extra_boot_args=EXTRA_BOOT_ARGS,
    )
    print(f"STAGE91_CI={CI_RUN} KERNEL_SHA={KERNEL_SHA256}")
    print(f"STAGE91_PAYLOAD={output}")


if __name__ == "__main__":
    main()
