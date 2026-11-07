import struct
import unittest
from pathlib import Path

from check_stage40_late_c import CHECKPOINTS, TARGET_PA, inspect
from check_stage21b_mmu import Payload


class LateCGuardTests(unittest.TestCase):
    def test_guard_accepts_rebuilt_kernel_and_rejects_modified_branch(self):
        path = Path(__file__).parent / "out/cactus/linux-chainload/stage28-relocated-payload.bin"
        raw = path.read_bytes()
        self.assertEqual(inspect(raw)[0], TARGET_PA)
        payload = Payload(raw)
        offset = payload.read(TARGET_PA, 4)
        self.assertEqual(struct.unpack("<I", offset)[0], 0x97FE7424)
        # Change only the instruction being replaced with the debug BRK.
        # A different kernel must fail preflight rather than being patched.
        mutated = bytearray(raw)
        needle = struct.pack("<I", 0x97FE7424)
        # Use the physical payload offset from its segment metadata.
        va = (payload.virt + TARGET_PA - payload.phys) & ((1 << 64) - 1)
        physical_offset, = (
            offset + va - segment_va
            for segment_va, _, offset, filesz in payload.segs
            if segment_va <= va and va + 4 <= segment_va + filesz
        )
        self.assertEqual(mutated[physical_offset:physical_offset + 4], needle)
        mutated[physical_offset] ^= 1
        with self.assertRaisesRegex(ValueError, "Stage40 XNU checkpoint drift"):
            inspect(bytes(mutated))

    def test_guard_pins_called_function_entry_and_return_site(self):
        path = Path(__file__).parent / "out/cactus/linux-chainload/stage28-relocated-payload.bin"
        raw = path.read_bytes()
        for stage in (41, 42, 43, 44):
            pa, va, expected = CHECKPOINTS[stage]
            self.assertEqual(inspect(raw, stage), (pa, va))
            data = bytearray(raw)
            payload = Payload(raw)
            target_va = (payload.virt + pa - payload.phys) & ((1 << 64) - 1)
            offset, = (
                off + target_va - seg_va
                for seg_va, _, off, filesz in payload.segs
                if seg_va <= target_va and target_va + 4 <= seg_va + filesz
            )
            self.assertEqual(struct.unpack_from("<I", data, offset)[0], expected)
            data[offset] ^= 1
            with self.assertRaisesRegex(ValueError, f"Stage(40|{stage}) XNU (startup|checkpoint) drift"):
                inspect(bytes(data), stage)


if __name__ == "__main__":
    unittest.main()
