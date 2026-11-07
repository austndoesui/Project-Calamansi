"""Distinguish COM25 pre-handoff delivery from real XNU EL1 execution."""
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from test_stage28_usb import trace28

HERE = Path(__file__).resolve().parent


def capture(*, native=True, handoff=True, correct_kernel=True):
    packets = []
    for start in range(0, len(trace28()), 56):
        pkt = bytearray(trace28()[start:start + 56])
        ev = struct.unpack_from("<I", pkt, 16)[0]
        if ev == 0x2700:
            struct.pack_into("<I", pkt, 16, 0x2800)
            struct.pack_into("<Q", pkt, 28,
                             0x1a0cf300cd5a6f86 if correct_kernel else 0)
        if ev == 0x2303 and not handoff:
            continue
        if ev == 0x20a1 and not native:
            break
        packets.append(pkt)
        if ev == 0x2700:
            flush = bytearray(pkt)
            struct.pack_into("<I", flush, 16, 0x3500)
            struct.pack_into("<QQQ", flush, 28,
                             0x8142d488, 0x824bc000, 2)
            packets.append(flush)
    assembled = bytearray()
    for index, pkt in enumerate(packets):
        pkt[6] = 35
        struct.pack_into("<I", pkt, 8, index)
        struct.pack_into("<I", pkt, 52, zlib.crc32(pkt[:52]))
        assembled.extend(pkt)
    return bytes(assembled)


class Stage35USB(unittest.TestCase):
    def test_handoff_marker_is_not_native_xnu_proof(self):
        with tempfile.TemporaryDirectory(dir=HERE / 'out/cactus') as temp:
            target = Path(temp) / "stage35.bin"
            command = [sys.executable, str(HERE / 'decode-cactus-usb.py'),
                       str(target), '--require-stage35', '--show', '0']

            def check(payload):
                target.write_bytes(payload)
                return subprocess.run(command, capture_output=True, text=True)

            delivered = check(capture(native=False))
            self.assertEqual(delivered.returncode, 2, delivered.stdout)
            self.assertIn('NATIVE XNU EXECUTION UNCONFIRMED', delivered.stdout)
            entered = check(capture())
            self.assertEqual(entered.returncode, 0, entered.stdout + entered.stderr)
            self.assertIn('NATIVE XNU EL1 ENTRY CONFIRMED', entered.stdout)
            for bad in (capture(handoff=False), capture(correct_kernel=False),
                        capture()[:-56*30]):
                result = check(bad)
                self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
