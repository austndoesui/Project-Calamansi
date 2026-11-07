#!/usr/bin/env python3
"""Fingerprint XNU patch inputs that can change generated/installhdrs output.

A patch touching exclusively C/assembly implementation files cannot alter
headers installed by XNU's installhdrs phase. Everything else, including
shell hooks and unknown patch syntax, conservatively invalidates this cache.
"""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "xnu" / "patches" / "manifest.json"
DIFF_HEADER = re.compile(rb"^diff --git a/([^\n]+) b/([^\n]+)$", re.MULTILINE)
IMPLEMENTATION_EXTS = {".c", ".s"}


def fingerprint() -> str:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["patches"]
    digest = hashlib.sha256(b"calamansi-xnu-installhdrs-v1\0")
    for entry in entries:
        path = ROOT / entry["source"]
        data = path.read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Patch manifest checksum mismatch: {entry['source']}")

        paths = DIFF_HEADER.findall(data)
        only_implementation = (
            path.suffix == ".patch"
            and bool(paths)
            and all(
                Path(after.decode("utf-8", errors="replace")).suffix.lower()
                in IMPLEMENTATION_EXTS
                for _, after in paths
            )
        )
        if not only_implementation:
            digest.update(entry["upstream_name"].encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(data).digest())

    return digest.hexdigest()


if __name__ == "__main__":
    print(fingerprint())
