import struct
import sys
from pathlib import Path

file = sys.argv[1]
out = sys.argv[2]

src = Path(file).read_bytes()
magic, total, header_size, entry_size, count, entries_offset, page_size, version = \
    struct.unpack_from(">8I", src)
assert magic == 0xd7b7ab1e, f"unexpected table magic: {magic:#x}"
assert count >= 1

dt_size, dt_offset = struct.unpack_from(">II", src, entries_offset)
assert dt_offset + dt_size <= len(src), "DTB entry extends past the table"

Path(out).write_bytes(
    src[dt_offset:dt_offset + dt_size]
)
print(f"Extracted entry 0: offset={dt_offset:#x}, size={dt_size:#x}")