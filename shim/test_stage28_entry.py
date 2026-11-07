"""Stage28 protects the exact rebuilt Mach-O pmap panic instruction."""
import unittest
from pathlib import Path
from check_stage21b_mmu import Payload
from check_stage28_pmap import inspect, PINS

FILE = Path(__file__).resolve().parent / 'out/cactus/stage27-relocated-payload.bin'


class Stage28Entry(unittest.TestCase):
    def test_new_kernel_pmap_and_edited_opcode_rejection(self):
        original = FILE.read_bytes()
        self.assertEqual(inspect(original), (0x81405218, 0xfffffff007405218))
        payload = Payload(original)
        for phys in PINS:
            va = payload.virt + phys - payload.phys
            idx = next(off + va - segva for segva, _, off, size in payload.segs
                       if segva <= va < segva + size - 3)
            damaged = bytearray(original)
            damaged[idx] ^= 1
            with self.assertRaises(ValueError, msg=f"{phys:#x}"):
                inspect(damaged)


if __name__ == '__main__':
    unittest.main()
