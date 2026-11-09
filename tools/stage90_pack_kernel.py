#!/usr/bin/env python3
"""Build Stage90 with the exact successful CI XNU and external iOS userdata."""
import hashlib
from pathlib import Path

import stage27_pack_kernel as pack

KERNEL_SHA256 = "376706e72c2f15eb81e4aeaa9222f9772aacadeb021e2d25e018959ee3ec664e"
ROOT_SHA256 = "cf281dccb5b69add3ef01070a3ed21202287727dffa982772fd705ff4acaeea9"
CI_RUN = "42474795094"
EXTRA_BOOT_ARGS = (
    "cactusroot=userdata cactusrw=1 rootrw=1 "
    "unentitled_ios_sim_launch=1 ignition_level=1 "
    "launchd_unsecure_cache=1 sweetfb_noconsole=1 "
    "wdt_test=no_user_checkin wdt=-1"
)


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    artifacts = project / "_build/_xnu-ci-worktree/_artifacts/run4"
    kernel = artifacts / "kernel.development.cactus"
    root = project / "_build/ios16-runtime/stage87-guestfs.hfs"
    output = project / "shim/out/cactus/payload-stage90.bin"
    if output.exists():
        raise SystemExit(f"refusing overwrite: {output}")
    if hashlib.sha256(kernel.read_bytes()).hexdigest() != KERNEL_SHA256:
        raise SystemExit("Stage90 CI kernel checksum differs")
    if f"{KERNEL_SHA256}  {kernel.name}" not in (artifacts / "SHA256SUMS").read_text():
        raise SystemExit("Stage90 CI SHA256SUMS differs")
    if root.stat().st_size != 16 * 1024 * 1024:
        raise SystemExit("Stage90 diagnostic HFS root size differs")
    with root.open("rb") as handle:
        handle.seek(1024)
        if handle.read(2) != b"H+":
            raise SystemExit("invalid HFS+ diagnostic root")
    if hashlib.sha256(root.read_bytes()).hexdigest() != ROOT_SHA256:
        raise SystemExit("Stage90 diagnostic HFS root checksum differs")
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
    print(f"STAGE90_CI={CI_RUN} KERNEL_SHA={KERNEL_SHA256}")
    print(f"STAGE90_PAYLOAD={output}")


if __name__ == "__main__":
    main()
