#!/usr/bin/env python3
"""Validate and stage iPhone X iOS 16 IPSW component files without flashing.

Extract into a new directory on a filesystem with adequate free space. Existing
outputs are never replaced, including when an earlier extraction was partial.
"""
import argparse
import hashlib
import json
import plistlib
import shutil
import zipfile
from pathlib import Path

EXPECTED_BUILD = "20H392"
EXPECTED_MODELS = {"iPhone10,3", "iPhone10,6"}
COMPONENTS = {"os": "OS", "systemos": "Cryptex1,SystemOS",
              "appos": "Cryptex1,AppOS", "kernelcache": "KernelCache"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipsw", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--extract", nargs="+", choices=COMPONENTS)
    parser.add_argument("--board", choices=("d22ap", "d221ap"), default="d22ap")
    args = parser.parse_args()
    if args.extract and not args.output:
        parser.error("--output is required for extraction")
    with zipfile.ZipFile(args.ipsw) as archive:
        manifest = plistlib.loads(archive.read("BuildManifest.plist"))
        build = manifest.get("ProductBuildVersion")
        models = set(manifest.get("SupportedProductTypes", []))
        if build != EXPECTED_BUILD or models != EXPECTED_MODELS:
            raise SystemExit(f"unexpected donor: {build=} {sorted(models)=}")
        identity = next((identity for identity in manifest["BuildIdentities"]
                         if identity.get("Info", {}).get("DeviceClass") == args.board
                         and identity.get("Info", {}).get("RestoreBehavior") == "Erase"), None)
        if identity is None:
            raise SystemExit(f"no Erase identity for {args.board}")
        report = {"build": build, "models": sorted(models), "board": args.board,
                  "components": {}}
        for label, manifest_key in COMPONENTS.items():
            archive_name = identity["Manifest"][manifest_key]["Info"]["Path"]
            entry = archive.getinfo(archive_name)
            report["components"][label] = {"archive_path": archive_name,
                  "size": entry.file_size, "zip_crc32": f"{entry.CRC:08x}"}
        if args.extract:
            args.output.mkdir(parents=True, exist_ok=True)
            required = sum(report["components"][item]["size"] for item in args.extract)
            free = shutil.disk_usage(args.output).free
            if free < required + 2 * 1024**3:
                raise SystemExit(f"insufficient free space: free={free}, required={required + 2 * 1024**3}")
            for label in args.extract:
                info = report["components"][label]
                source = info["archive_path"]
                target = args.output / (label + Path(source).suffix)
                if target.exists():
                    raise SystemExit(f"refusing to overwrite {target}")
                digest = hashlib.sha256()
                try:
                    with archive.open(source) as src, target.open("xb") as dst:
                        while chunk := src.read(4 * 1024 * 1024):
                            dst.write(chunk)
                            digest.update(chunk)
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
                info["sha256"] = digest.hexdigest()
                info["extracted_to"] = str(target)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
