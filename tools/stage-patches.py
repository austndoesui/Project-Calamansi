#!/usr/bin/env python3
"""Verify Calamansi's ordered patch manifest and stage legacy-compatible names.

The upstream XNU builder iterates a flat patches directory by name; the
canonical files here are organized by scope. Device builds can stage only
their own patches plus common/legacy patches. Never silently skip entries.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "xnu/patches/manifest.json"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Directory for flat legacy filenames")
    parser.add_argument(
        "--device",
        choices=("CACTUS", "OPPO6765"),
        help="stage common/legacy patches plus only this device's patches",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.output is None and not args.verify_only:
        parser.error("pass --output or --verify-only")
    rows = json.loads(MANIFEST.read_text())["patches"]
    if not rows:
        raise SystemExit("empty patch manifest")
    names, sources, last = set(), set(), -1
    for row in rows:
        n = int(row["order"])
        name = row["upstream_name"]
        rel = Path(row["source"])
        if n < last or name in names or rel in sources:
            raise SystemExit(f"duplicate or unordered manifest entry: {name}")
        if rel.is_absolute() or ".." in rel.parts or rel.parts[:2] != ("xnu", "patches"):
            raise SystemExit(f"invalid patch path: {rel}")
        names.add(name); sources.add(rel); last = n
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"missing patch file: {src}")
        content = src.read_bytes().replace(b"\r\n", b"\n")
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != row["sha256"]:
            raise SystemExit(f"checksum mismatch: {name}: {checksum}")
    actual = {p.relative_to(ROOT) for p in (ROOT/"xnu/patches").rglob("*")
              if p.is_file() and p.suffix in (".patch",".sh")}
    if actual != sources:
        raise SystemExit(f"manifest differs from tree: missing={sources-actual}; extra={actual-sources}")
    if args.output is not None:
        selected = []
        for row in rows:
            rel = Path(row["source"])
            parts = rel.parts
            include = True
            if args.device is not None and len(parts) >= 4 and parts[2] == "devices":
                target = args.device.lower()
                owner = parts[3]
                # OPPO6765 has an independent compile-profile patch. Cactus
                # patches contain board-specific VM and early-boot behavior.
                include = owner == target
            if include:
                selected.append(row)

        args.output.mkdir(parents=True, exist_ok=True)
        selected_names = {row["upstream_name"] for row in selected}
        # Remove stale files previously staged from this manifest while leaving
        # any patches supplied by the upstream build-script repository intact.
        for row in rows:
            target = args.output / row["upstream_name"]
            if row["upstream_name"] not in selected_names and target.exists():
                target.unlink()
        for row in selected:
            target = args.output / row["upstream_name"]
            # Preserve the upstream builder's original overwrite behavior.
            target.write_bytes((ROOT / row["source"]).read_bytes().replace(b"\r\n", b"\n"))
        print(f"STAGED {len(selected)} manifest entries for {args.device or 'all devices'} in {args.output}")
    print(f"PATCH MANIFEST VERIFIED: {len(rows)} files; {len([r for r in rows if r['source'].endswith('.patch')])} patches")

if __name__ == "__main__":
    main()
