"""Stage27's corrected XNU image must not be confused with Stage22's."""
import unittest
from pathlib import Path

from check_stage27_entry import inspect, CHANGED_CALL_PA, CHANGED_PROLOGUE_PA
from check_stage21b_mmu import Payload

ROOT = Path(__file__).resolve().parent


class Stage27Entry(unittest.TestCase):
    def test_new_macho_guard_checks_actual_recompiled_instructions(self):
        raw = (ROOT / 'out/cactus/stage27-relocated-payload.bin').read_bytes()
        self.assertEqual(inspect(raw),
                         (0xFFFFFFF00742D488, 0xFFFFFFF007AC0C0C))
        old = (ROOT / 'out/cactus/linux-chainload/stage18-payload.bin').read_bytes()
        with self.assertRaises(ValueError):
            inspect(old)
        p = Payload(raw)
        for physical in (CHANGED_CALL_PA, CHANGED_PROLOGUE_PA):
            virtual = p.virt + physical - p.phys
            offset = next(off + virtual - va for va, _, off, size in p.segs
                          if va <= virtual < va + size - 3)
            mutated = bytearray(raw)
            mutated[offset] ^= 1
            with self.assertRaises(ValueError, msg=f'{physical:#x}'):
                inspect(mutated)


if __name__ == '__main__':
    unittest.main()
