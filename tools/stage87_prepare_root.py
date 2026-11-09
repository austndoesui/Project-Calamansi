#!/usr/bin/env python3
"""Rebuild the Stage87 HFS+ boot root from the pinned Stage86 base and donor.

Requires WSL Ubuntu with guestfish and the read-only APFS donor OS mounted.
Never changes the original Stage86 image or either donor filesystem.
"""

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

BASE_SHA256 = "1a64ae893082d3def930dba358c28c2a3a5b51b98b465152479144431666c68a"
PLIST_RELATIVE_PATHS = (
    "System/Library/xpc/launchd.plist",
    "System/Library/CoreServices/SystemVersion.plist",
)
DIRECTORIES = (
    "/dev", "/private/etc", "/private/var", "/private/var/tmp",
    "/private/var/run", "/private/var/db", "/System/Library/xpc",
    "/System/Library/Caches/com.apple.dyld", "/Library/Preferences",
)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def guestfish(image, commands):
    args = ["guestfish", "--rw", "-a", str(image), "run", ":",
            "mount", "/dev/sda", "/"]
    for command in commands:
        args.extend((":", *command))
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--base", type=Path,
                        default=project / "_build/ios16-runtime/stage86-guestfs.hfs")
    parser.add_argument("--donor-os", type=Path,
                        default=Path("/home/lapdq/calamansi-mount/os/root"))
    parser.add_argument("--output", type=Path,
                        default=project / "_build/ios16-runtime/stage87-guestfs.hfs")
    args = parser.parse_args()
    if checksum(args.base) != BASE_SHA256:
        parser.error("Stage86 input root SHA256 mismatch")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing root: {args.output}")
    for item in PLIST_RELATIVE_PATHS:
        if not (args.donor_os / item).is_file():
            parser.error(f"donor file missing: {args.donor_os / item}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.base, args.output)
    try:
        operations = [["mkdir-p", directory] for directory in DIRECTORIES]
        for virtual, target in (("/var", "private/var"),
                                ("/tmp", "private/var/tmp")):
            operations += [["mkdir-p", virtual], ["rmdir", virtual],
                           ["ln-s", target, virtual]]
        operations.append(["ln-s", "private/etc", "/etc"])
        for item in PLIST_RELATIVE_PATHS:
            operations.append(["upload", str(args.donor_os / item), "/" + item])
        guestfish(args.output, operations)
        subprocess.run(["guestfish", "--ro", "-a", str(args.output), "run", ":",
                        "mount", "/dev/sda", "/", ":", "ll", "/"], check=True)
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    print(f"STAGE87 ROOT size={args.output.stat().st_size} sha256={checksum(args.output)}")


if __name__ == "__main__":
    main()
