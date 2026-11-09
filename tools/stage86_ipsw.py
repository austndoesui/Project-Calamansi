#!/usr/bin/env python3
"""Inspect an iPhone 8 iOS 16 IPSW, or extract selected component images.

This is a host-side preparation tool. It never modifies the IPSW or flashes a
device, and makes no assumptions about which image will fit in the boot RAM.
"""
import argparse
import hashlib
import json
import plistlib
import shutil
import zipfile
from pathlib import Path


COMPONENTS = {
    "os": "OS",
    "systemos": "Cryptex1,SystemOS",
    "appos": "Cryptex1,AppOS",
    "kernelcache": "KernelCache",
}


def inspect(ipsw: Path):
    with zipfile.ZipFile(ipsw) as archive:
        manifest = plistlib.loads(archive.read("BuildManifest.plist"))
        models = set(manifest.get("SupportedProductTypes", []))
        if manifest.get("ProductBuildVersion") != "20H392" or models != {"iPhone10,1", "iPhone10,4"}:
            raise ValueError(f"unexpected donor build/models: {manifest.get('ProductBuildVersion')}, {models}")
        identity = next((i for i in manifest["BuildIdentities"]
                         if i.get("Info", {}).get("DeviceClass") == "d201ap"), None)
        if identity is None:
            raise ValueError("missing iPhone 8 d201ap build identity")
        result = {}
        for name, key in COMPONENTS.items():
            path = identity["Manifest"][key]["Info"]["Path"]
            info = archive.getinfo(path)
            result[name] = {"path": path, "bytes": info.file_size,
                            "compressed_bytes": info.compress_size}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipsw", type=Path)
    parser.add_argument("--out", type=Path, help="directory for extracted selected images")
    parser.add_argument("--extract", nargs="+", choices=sorted(COMPONENTS),
                        help="select images; omit to inspect without extracting")
    args = parser.parse_args()
    components = inspect(args.ipsw)
    print(json.dumps(components, indent=2))
    if not args.extract:
        return
    if args.out is None:
        parser.error("--out required for --extract")
    args.out.mkdir(parents=True, exist_ok=True)
    required = sum(components[k]["bytes"] for k in args.extract)
    if shutil.disk_usage(args.out).free < required + 1024**3:
        raise SystemExit(f"insufficient free space: need {required + 1024**3} bytes including 1 GiB reserve")
    with zipfile.ZipFile(args.ipsw) as archive:
        for key in args.extract:
            name = components[key]["path"]
            dest = args.out / f"ios16-20H392-{key}{Path(name).suffix}"
            if dest.exists():
                raise SystemExit(f"refusing to overwrite {dest}")
            digest = hashlib.sha256()
            try:
                with archive.open(name) as src, dest.open("xb") as dst:
                    while data := src.read(1024 * 1024):
                        dst.write(data)
                        digest.update(data)
            except BaseException:
                dest.unlink(missing_ok=True)
                raise
            print(f"EXTRACTED {key}: {dest} sha256={digest.hexdigest()}")


if __name__ == "__main__":
    main()
