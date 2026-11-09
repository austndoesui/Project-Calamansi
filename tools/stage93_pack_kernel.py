#!/usr/bin/env python3
"""Package a verified CI XNU with the tested cactus eMMC/HFS shim ABI.

The kernel is an explicitly SHA-pinned GitHub Actions artifact. The small,
verified Stage87 HFS image remains a fallback ramdisk; the actual iPhone X
root lives on userdata and is not rebuilt or modified by this script.
"""
import argparse
import hashlib
from pathlib import Path

import stage27_pack_kernel as pack
from stage90_pack_kernel import EXTRA_BOOT_ARGS, ROOT_SHA256


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=(93, 94, 96), default=93,
                        help="versioned payload output (never overwrite a tested stage)")
    parser.add_argument("--kernel", type=Path, required=True,
                        help="kernel.development.cactus extracted from the Stage93 CI run")
    parser.add_argument("--sha256", required=True,
                        help="verified 64-character SHA256 of the CI kernel")
    parser.add_argument("--sums", type=Path, required=True,
                        help="original SHA256SUMS from the same CI artifact")
    parser.add_argument("--ci-run", required=True, help="successful GitHub Actions run ID")
    args = parser.parse_args()
    if len(args.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in args.sha256):
        parser.error("--sha256 must be a lowercase 64-character hex digest")
    if not args.ci_run.isdecimal():
        parser.error("--ci-run must be the numeric GitHub Actions run ID")

    project = Path(__file__).resolve().parents[1]
    kernel = args.kernel.resolve()
    root = project / "_build/ios16-runtime/stage87-guestfs.hfs"
    output = project / f"shim/out/cactus/payload-stage{args.stage}.bin"
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing Stage{args.stage} payload: {output}")
    if not kernel.is_file() or not args.sums.is_file() or not root.is_file():
        raise SystemExit("missing CI kernel, SHA256SUMS or pinned fallback HFS")
    if sha256_file(kernel) != args.sha256:
        raise SystemExit("CI kernel checksum differs")
    if f"{args.sha256}  {kernel.name}" not in args.sums.read_text():
        raise SystemExit("kernel does not match CI SHA256SUMS")
    if root.stat().st_size != 16 * 1024 * 1024 or sha256_file(root) != ROOT_SHA256:
        raise SystemExit("fallback HFS bytes differ from verified Stage91")

    pack.STAGE77_VERIFIED_KERNEL_SHA256 = args.sha256
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
    print(f"STAGE{args.stage}_CI={args.ci_run} KERNEL_SHA256={args.sha256}")
    print(f"STAGE{args.stage}_PAYLOAD={output} SHA256={sha256_file(output)}")


if __name__ == "__main__":
    main()
