#!/usr/bin/env python3
"""Exact allowlist cleanup of obsolete iPhone 8 and iPhone X staging files.

Only invoked by cleanup-iphone8-assets.ps1. Default is preview.
"""
import os
import pathlib
import shutil
import sys

BASE = pathlib.Path("/home/lapdq")
ALLOWED = {
    "calamansi-ios16-root-diagnostic.hfs",
    "calamansi-ios16-sweet-prepared.hfs",
    "calamansi-ios16-sweet-v1.hfs",
    "calamansi-ios16-extracted",
    "calamansi-osroot-extracted",
    "calamansi-systemos-extracted",
    "calamansi-appos-extracted",
    "calamansi-dyld-verified",
    "calamansi-ipsw-temp",
    "calamansi-iphone-x-20H392/calamansi-iphone-x-root-INCOMPLETE.hfs",
    "calamansi-iphone-x-20H392/os.raw.img",
}

IPHONE_X_FINAL = BASE / "calamansi-iphone-x-20H392" / "calamansi-iphone-x-root-20H392.hfs"
IPHONE_X_SPARSE = BASE / "calamansi-iphone-x-20H392" / "ios16-iphone-x-20H392-userdata.simg"


def allocated(path: pathlib.Path) -> int:
    st = path.lstat()
    total = st.st_blocks * 512
    if path.is_dir() and not path.is_symlink():
        for root, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                try:
                    total += (pathlib.Path(root) / name).lstat().st_blocks * 512
                except FileNotFoundError:
                    pass
    return total


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("preview", "execute"):
        sys.exit("usage: cleanup-iphone8-wsl.py preview|execute EXACT_NAMES...")
    execute = sys.argv[1] == "execute"
    names = sys.argv[2:]
    if len(names) != len(set(names)) or set(names) - ALLOWED:
        sys.exit("Safety stop: unrecognized or duplicate WSL targets")
    if not BASE.is_dir() or BASE.is_symlink():
        sys.exit("Safety stop: invalid WSL home")
    if any(name.startswith("calamansi-iphone-x-20H392/") for name in names):
        if (not IPHONE_X_FINAL.is_file() or IPHONE_X_FINAL.is_symlink()
                or IPHONE_X_FINAL.stat().st_size != 16 * 1024**3
                or not IPHONE_X_SPARSE.is_file() or IPHONE_X_SPARSE.is_symlink()):
            sys.exit("Safety stop: final iPhone X HFS and sparse image must be present")

    mountpoints = set()
    with open("/proc/self/mountinfo", encoding="utf-8") as source:
        for line in source:
            parts = line.split()
            if len(parts) > 4:
                mountpoints.add(parts[4].replace("\\040", " "))

    targets = []
    for name in names:
        path = BASE / name
        if path.parent != BASE and (path.parent.is_symlink() or not path.parent.is_dir()):
            sys.exit(f"Safety stop: invalid iPhone X staging parent for {path}")
        if not path.exists() and not path.is_symlink():
            print("ABSENT", path, flush=True)
            continue
        if path.is_symlink():
            sys.exit(f"Safety stop: symlink target {path}")
        prefix = str(path)
        if any(m == prefix or m.startswith(prefix + "/") for m in mountpoints):
            sys.exit(f"Safety stop: active mount under {path}; unmount first")
        targets.append(path)
        print(
            "DELETE" if execute else "PREVIEW",
            f"{allocated(path) / (1024**3):.2f} GiB",
            path,
            flush=True,
        )

    if execute:
        for path in targets:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        print("WSL CLEANUP COMPLETE", flush=True)
    else:
        print("WSL PREVIEW COMPLETE (no files removed)", flush=True)


if __name__ == "__main__":
    main()
