#!/usr/bin/env python3
"""Read-only ARM64 Mach-O load-command audit for an extracted iOS donor.

Unlike a general object dumper this reports the concrete dependencies that
Calamansi's root filesystem, kernel Mach-O loader and dyld must support.
"""

import argparse
import json
import struct
from pathlib import Path


MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLINKER = 0x0E
LC_CODE_SIGNATURE = 0x1D
LC_MAIN = 0x80000028
LC_BUILD_VERSION = 0x32
LC_DYLD_CHAINED_FIXUPS = 0x80000034
LC_DYLD_EXPORTS_TRIE = 0x80000033
LC_DYLD_INFO_ONLY = 0x80000022
LIBRARY_COMMANDS = {
    0x0C: "load", 0x80000018: "weak", 0x8000001F: "reexport",
    0x80000023: "upward", 0x8000001C: "rpath",
}


def load_string(data: bytes, cmd_offset: int, cmdsize: int, string_offset: int) -> str:
    if string_offset < 12 or string_offset >= cmdsize:
        raise ValueError(f"bad load-command string offset {string_offset}")
    raw = data[cmd_offset + string_offset:cmd_offset + cmdsize]
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


def audit(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError(f"{path}: truncated Mach-O header")
    magic, cpu, subtype, filetype, ncmds, sizeofcmds, flags, _ = struct.unpack_from("<8I", data)
    if magic != MH_MAGIC_64 or cpu != CPU_TYPE_ARM64:
        raise ValueError(f"{path}: expected thin ARM64 Mach-O, got {magic:#x}/{cpu:#x}")
    if 32 + sizeofcmds > len(data) or ncmds > 4096:
        raise ValueError(f"{path}: invalid Mach-O commands")
    result = {
        "path": str(path), "bytes": len(data), "filetype": filetype,
        "cpu_subtype": subtype, "ncmds": ncmds, "flags": flags,
        "dylinker": None, "libraries": [], "segments": [], "entryoff": None,
        "code_signature": None, "build_version": None,
        "chained_fixups": False, "exports_trie": False, "dyld_info_only": False,
    }
    pos = 32
    for _ in range(ncmds):
        if pos + 8 > 32 + sizeofcmds:
            raise ValueError(f"{path}: load-command count exceeds header")
        command, size = struct.unpack_from("<II", data, pos)
        if size < 8 or pos + size > 32 + sizeofcmds:
            raise ValueError(f"{path}: invalid load-command size")
        if command == LC_SEGMENT_64:
            if size < 72:
                raise ValueError(f"{path}: short LC_SEGMENT_64")
            name, vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<16sQQQQ", data, pos + 8)
            result["segments"].append({
                "name": name.split(b"\0")[0].decode("ascii", "replace"),
                "vmaddr": vmaddr, "vmsize": vmsize,
                "fileoff": fileoff, "filesize": filesize,
            })
        elif command in LIBRARY_COMMANDS or command == LC_LOAD_DYLINKER:
            if size < 12:
                raise ValueError(f"{path}: short dylib/dylinker command")
            off, = struct.unpack_from("<I", data, pos + 8)
            target = load_string(data, pos, size, off)
            if command == LC_LOAD_DYLINKER:
                result["dylinker"] = target
            else:
                result["libraries"].append({"kind": LIBRARY_COMMANDS[command], "path": target})
        elif command == LC_MAIN:
            if size < 24:
                raise ValueError(f"{path}: short LC_MAIN")
            result["entryoff"], = struct.unpack_from("<Q", data, pos + 8)
        elif command == LC_CODE_SIGNATURE:
            if size < 16:
                raise ValueError(f"{path}: short LC_CODE_SIGNATURE")
            off, length = struct.unpack_from("<II", data, pos + 8)
            if off + length > len(data):
                raise ValueError(f"{path}: code signature beyond EOF")
            result["code_signature"] = {"offset": off, "bytes": length}
        elif command == LC_BUILD_VERSION:
            if size < 24:
                raise ValueError(f"{path}: short LC_BUILD_VERSION")
            platform, minos, sdk, ntools = struct.unpack_from("<IIII", data, pos + 8)
            result["build_version"] = {"platform": platform, "minimum_os": minos, "sdk": sdk, "tools": ntools}
        elif command == LC_DYLD_CHAINED_FIXUPS:
            result["chained_fixups"] = True
        elif command == LC_DYLD_EXPORTS_TRIE:
            result["exports_trie"] = True
        elif command == LC_DYLD_INFO_ONLY:
            result["dyld_info_only"] = True
        pos += size
    if pos != 32 + sizeofcmds:
        raise ValueError(f"{path}: load command size mismatch")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = {str(path): audit(path) for path in args.files}
    encoded = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
