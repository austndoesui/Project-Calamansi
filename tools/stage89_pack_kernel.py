#!/usr/bin/env python3
"""Stage89: package CI-verified native cactus MSDC XNU with Stage87 HFS root.

This build must use the exact successful GitHub Actions kernel. The existing
Stage27 packer's SHA checks remain enabled, with their expected identities
set to the new audited artifact and unchanged Stage87 HFS image.
"""
import hashlib
from pathlib import Path

import stage27_pack_kernel as pack


KERNEL_SHA256 = "3fa61a4f8a246abb08e53a8770175959e21d284d7509b70098c3922503318a7a"
RUN3 = "42465942432"


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    artifacts = project / "_build/_xnu-ci-worktree/_artifacts/run3"
    kernel = artifacts / "kernel.development.cactus"
    root = project / "_build/ios16-runtime/stage87-guestfs.hfs"
    output = project / "shim/out/cactus/payload-stage89.bin"
    if output.exists():
        raise SystemExit(f"refusing overwrite: {output}")
    kernel_sha = hashlib.sha256(kernel.read_bytes()).hexdigest()
    if kernel_sha != KERNEL_SHA256:
        raise SystemExit(f"unexpected Stage89 kernel hash: {kernel_sha}")
    if not any(line.split()[-1].lstrip("*") == kernel.name and
               line.split()[0] == KERNEL_SHA256
               for line in (artifacts / "SHA256SUMS").read_text().splitlines()):
        raise SystemExit("CI kernel artifact SHA256SUMS mismatch")
    if root.stat().st_size != 16 * 1024 * 1024:
        raise SystemExit("Stage87 baseline HFS+ root size changed")
    with root.open("rb") as handle:
        handle.seek(1024)
        if handle.read(2) != b"H+":
            raise SystemExit("Stage87 baseline root signature changed")
    root_sha = hashlib.sha256(root.read_bytes()).hexdigest()
    if root_sha != "cf281dccb5b69add3ef01070a3ed21202287727dffa982772fd705ff4acaeea9":
        raise SystemExit(f"Stage87 audited root checksum changed: {root_sha}")
    pack.STAGE77_VERIFIED_KERNEL_SHA256 = KERNEL_SHA256
    pack.STAGE65_VERIFIED_INIT_SHA256 = root_sha
    pack.prepare(kernel, project / "shim/out/cactus/payload.bin", output,
                 stage61_live_fb=True, stage64_cactus_gic=True,
                 stage65_cactus_pid1=True, stage66_topbar=True,
                 stage67_vfs_probe=True, stage68_root_pid1=True,
                 stage69_root_pid1=True, stage70_minimal_pid1=True,
                 stage71_direct_pid1=True, stage72_mockfs_pid1=True,
                 stage73_pid1_vm=True, stage74_physmap_pid1=True,
                 stage75_exec_read=True, stage76_pid1_shadow=True,
                 stage77_pid1_wired=True, ramdisk=root,
                 extra_boot_args=("unentitled_ios_sim_launch=1 "
                                  "sweetfb_noconsole=1 cactus_emmc_probe=1"))
    print(f"STAGE89_SHA256_VERIFIED={kernel_sha} CI_RUN={RUN3}")
    print(f"STAGE89_ROOT_SHA256={root_sha}")
    print(f"STAGE89_PAYLOAD={output}")


if __name__ == "__main__":
    main()
