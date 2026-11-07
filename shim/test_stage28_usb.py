"""Stage28 must prove the rebuilt kernel and real missing-PTE provenance."""
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from test_stage25_usb import trace as old_trace

HERE = Path(__file__).resolve().parent


def trace28(*, omit=None, bad_kernel=False):
    base = old_trace()
    records = []
    for offset in range(0, len(base), 56):
        pkt = bytearray(base[offset:offset+56])
        ev = struct.unpack_from("<I", pkt, 16)[0]
        if ev == omit:
            continue
        if ev == 0x2407:
            struct.pack_into("<Q", pkt, 44, 33)
        records.append(pkt)
        if ev == 0x2303 and omit != 0x2700:
            signed = bytearray(pkt)
            struct.pack_into("<I", signed, 16, 0x2700)
            struct.pack_into("<QQQ", signed, 28,
                             0 if bad_kernel else 0xa1b8677a3449664f,
                             0x8142d488, 0x824bc000)
            records.append(signed)
    result = bytearray()
    for i, pkt in enumerate(records):
        pkt[6] = 33
        struct.pack_into("<I", pkt, 8, i)
        struct.pack_into("<Q", pkt, 20, 13*i)
        struct.pack_into("<I", pkt, 52, zlib.crc32(pkt[:52]))
        result += pkt
    return bytes(result)


class Stage28USB(unittest.TestCase):
    def test_rebuilt_provenance_and_exact_pmap_fault(self):
        with tempfile.TemporaryDirectory(dir=HERE/'out/cactus') as root:
            path = Path(root) / "stage28-capture.bin"
            args = [sys.executable, str(HERE/'decode-cactus-usb.py'),
                    str(path), '--require-stage28', '--show', '0']

            def validate(data):
                path.write_bytes(data)
                return subprocess.run(args, capture_output=True, text=True)

            good = validate(trace28())
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            self.assertIn("STAGE28 NULL-PTE REQUEST CAPTURED", good.stdout)
            for bad in (trace28(omit=0x2700), trace28(bad_kernel=True),
                        trace28(omit=0x2502), trace28(omit=0x2507),
                        trace28()[:-56]):
                result = validate(bad)
                self.assertNotEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
