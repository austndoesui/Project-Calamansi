"""Stage49 display classification must distinguish safe skip from real pixel proof."""
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_decoder_spec = spec_from_file_location(
    "cactus_usb_decoder", Path(__file__).parent / "decode-cactus-usb.py")
_decoder = module_from_spec(_decoder_spec)
_decoder_spec.loader.exec_module(_decoder)
inspect_stage49 = _decoder.inspect_stage49


def sample(physical=False, written=False, stage=49):
    events = [0x1900, 0x4500, 0x4700, 0x4801, 0x4802,
              0x4900, 0x4901]
    if stage == 62:
        events[1:1] = [0x6200, 0x6201, 0x6202]
    if written:
        events.append(0x4902)
        if stage in (50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62):
            events.append(0x5000)
            if stage in (51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62):
                events.append(0x5100)
                if stage == 52:
                    events.append(0x5200)
                elif stage == 53:
                    events.append(0x5300)
                elif stage == 54:
                    events.append(0x5400)
                elif stage == 55:
                    events.append(0x5500)
                elif stage == 56:
                    events.append(0x5600)
                elif stage == 57:
                    events.append(0x5700)
                elif stage == 58:
                    events.append(0x5800)
                elif stage == 59:
                    events.append(0x5900)
                elif stage == 60:
                    events.append(0x6000)
                elif stage in (61, 62):
                    events.append(0x6100)
    events += [0x2303, 0x2800, 0x3500, 0x3900]
    records = []
    for i, ev in enumerate(events):
        a, b, c = 0, 0, 0
        if ev == 0x6200:
            a, b, c = 0, (0x30 << 32) | 0x1f, 0x0C100000
        elif ev == 0x6201:
            a, b, c = 0x0C100000, 0x30, 0x10
        elif ev == 0x6202:
            a, b, c = 0x01000000, 0x0B100000, 0x0C100000
        elif ev == 0x4801:
            a, b, c = 0x700000003, 0x7F0D0000, 0xE20000
        elif ev == 0x4802:
            a = {51: 0x81AC0C88, 52: 0x81AC3C88, 53: 0x81AC2F88,
                 54: 0x81AC30D8, 55: 0x81AC3138,
                 56: 0x81AC31E8, 57: 0x81AC33C8,
                 58: 0x81AC36F8, 59: 0x81AC37D8, 60: 0x81AC38F8, 61: 0x81AC3908, 62: 0x81AC3908}.get(stage, 0x81AC0C68)
            b, c = {52: 0xB0FFB5A8, 53: 0xD0FFB5A8,
                    54: 0xB0FFB5A8, 55: 0xB0FFB5A8,
                    56: 0xB0FFB5A8, 57: 0xB0FFB5A8,
                    58: 0xB0FFB5A8, 59: 0xB0FFB5A8, 60: 0xB0FFB5A8, 61: 0xB0FFB5A8, 62: 0xB0FFB5A8}.get(stage, 0x90FFB5C8), 1
        elif ev == 0x4900:
            a, b, c = 0x14003380, 0 if physical else 1, int(physical)
        elif ev == 0x4901:
            a, b, c = int(physical), 1, 7
        elif ev == 0x4902:
            a, b, c = 0xFF00FF00, 0xFFFF00FF, 1
        elif ev == 0x5000:
            a, b, c = 0x5E605000, 0x7F4DB000, 1
        elif ev == 0x5100:
            a, b, c = 0x7F4DB000, (0x824BC000 if stage == 52 else 0x824BB000), 4188
        elif ev == 0x5200:
            a, b, c = 0x7F4DB000, 0x81430488, 0x945E61817C333218
        elif ev == 0x5300:
            a, b, c = 0x7F4DB000, 0x8142D488, 0x361846AAB01F8040
        elif ev == 0x5400:
            a, b, c = 0x7F4DB000, 0x8142D488, 0xED5123CEE5377846
        elif ev == 0x5500:
            a, b, c = 0x7F4DB000, 0x8142D488, 0xEA16FAA6D49EB135
        elif ev == 0x5600:
            a, b, c = 0x7F4DB000, 0x8142D488, 0x3004D4478977B6B2
        elif ev == 0x5700:
            a, b, c = 0x7F4DB000, 0x8142D488, 0x7A0B778D113B3A66
        elif ev == 0x5800:
            a, b, c = 0x7F4DB000, 0x8142D488, 0x9D6977D4F44B9216
        elif ev == 0x5900:
            a, b, c = 0x7F4DB000, 0x8142D488, 0xED3074CC9E889F88
        elif ev == 0x6000:
            a, b, c = 0x7F4DB000, 0x8142D488, 0x2F3B02C004763C7A
        elif ev == 0x6100:
            a, b, c = 0x7F4DB000, 0x8142D488, 0x15FDBDAB0AA0CB1F
        elif ev == 0x2800:
            a = {51: 0x40F672D3500699B6, 52: 0x945E61817C333218,
                 53: 0x361846AAB01F8040, 54: 0xED5123CEE5377846,
                 55: 0xEA16FAA6D49EB135,
                 56: 0x3004D4478977B6B2,
                 57: 0x7A0B778D113B3A66,
                 58: 0x9D6977D4F44B9216,
                 59: 0xED3074CC9E889F88, 60: 0x2F3B02C004763C7A,
                 61: 0x15FDBDAB0AA0CB1F, 62: 0x15FDBDAB0AA0CB1F}.get(stage, 0x1A0CF300CD5A6F86)
        records.append(dict(stage=stage, event=ev, a=a, b=b, c=c, seq=i))
    return records


class Stage49USBTests(unittest.TestCase):
    def test_stage62_gicr_raw_census_precedes_xnu(self):
        records = sample(physical=True, written=True, stage=62)
        ok, reason = inspect_stage49(records, 62)
        self.assertTrue(ok, reason)
        for ev, key, bad in ((0x6202, 'c', 0),
                             (0x6201, 'a', 0x0C300000),
                             (0x2800, 'a', 0x2F3B02C004763C7A),
                             (0x4802, 'a', 0x81AC38F8)):
            bad_records = sample(physical=True, written=True, stage=62)
            next(r for r in bad_records if r['event'] == ev)[key] = bad
            self.assertFalse(inspect_stage49(bad_records, 62)[0])
        for ev in (0x6200, 0x6201, 0x6202):
            self.assertFalse(inspect_stage49(
                [r for r in records if r['event'] != ev], 62)[0])

    def test_stage61_gicr_frame_kernel_identity(self):
        baseline = sample(physical=True, written=True, stage=61)
        ok, reason = inspect_stage49(baseline, 61)
        self.assertTrue(ok, reason)
        for event, field, bad in (
                (0x6100, "c", 0x2F3B02C004763C7A),
                (0x4802, "a", 0x81AC38F8),
                (0x4802, "b", 0xD0FFB5A8),
                (0x2800, "a", 0x2F3B02C004763C7A)):
            tampered = sample(physical=True, written=True, stage=61)
            next(r for r in tampered if r["event"] == event)[field] = bad
            self.assertFalse(inspect_stage49(tampered, 61)[0])
        self.assertFalse(inspect_stage49(
            [r for r in baseline if r["event"] != 0x6100], 61)[0])

    def test_stage60_sgi8_kernel_identity(self):
        records=sample(physical=True,written=True,stage=60)
        self.assertTrue(inspect_stage49(records,60)[0])
        for event,field,bad in ((0x6000,"c",0xED3074CC9E889F88),
                                 (0x4802,"a",0x81AC37D8),
                                 (0x2800,"a",0xED3074CC9E889F88)):
            tampered=sample(physical=True,written=True,stage=60)
            next(r for r in tampered if r["event"]==event)[field]=bad
            self.assertFalse(inspect_stage49(tampered,60)[0])
        self.assertFalse(inspect_stage49(
            [r for r in records if r["event"]!=0x6000],60)[0])


    def test_stage59_irq_wait_kernel_identity(self):
        records=sample(physical=True,written=True,stage=59)
        self.assertTrue(inspect_stage49(records,59)[0])
        for event,field,bad in ((0x5900,"c",0x9D6977D4F44B9216),
                                 (0x4802,"a",0x81AC36F8),
                                 (0x2800,"a",0x9D6977D4F44B9216)):
            tampered=sample(physical=True,written=True,stage=59)
            next(r for r in tampered if r["event"]==event)[field]=bad
            self.assertFalse(inspect_stage49(tampered,59)[0])
        self.assertFalse(inspect_stage49(
            [r for r in records if r["event"]!=0x5900],59)[0])


    def test_stage58_gicv3_kernel_identity(self):
        records = sample(physical=True, written=True, stage=58)
        self.assertTrue(inspect_stage49(records, 58)[0])
        for event, field, wrong in (
            (0x5800, "c", 0x7A0B778D113B3A66),
            (0x4802, "a", 0x81AC31E8),
            (0x2800, "a", 0x7A0B778D113B3A66),
        ):
            wrong_records = sample(physical=True, written=True, stage=58)
            next(r for r in wrong_records if r["event"] == event)[field] = wrong
            self.assertFalse(inspect_stage49(wrong_records, 58)[0])
        self.assertFalse(inspect_stage49(
            [r for r in records if r["event"] != 0x5800], 58)[0])

    def test_stage57_kernel_irq_boot_identity(self):
        records = sample(physical=True, written=True, stage=57)
        self.assertTrue(inspect_stage49(records, 57)[0])
        for event, field, wrong in (
            (0x5700, "c", 0x3004D4478977B6B2),
            (0x4802, "a", 0x81AC31E8),
            (0x2800, "a", 0x3004D4478977B6B2),
        ):
            modified = sample(physical=True, written=True, stage=57)
            next(r for r in modified if r["event"] == event)[field] = wrong
            self.assertFalse(inspect_stage49(modified, 57)[0])
        self.assertFalse(inspect_stage49(
            [r for r in records if r["event"] != 0x5700], 57)[0])

    def test_stage56_diagnostic_kernel_identity(self):
        baseline = sample(physical=True, written=True, stage=56)
        self.assertTrue(inspect_stage49(baseline, 56)[0])
        for event, field, wrong in (
            (0x5600, "c", 0xEA16FAA6D49EB135),
            (0x4802, "a", 0x81AC30D8),
            (0x2800, "a", 0x361846AAB01F8040),
        ):
            bad = sample(physical=True, written=True, stage=56)
            next(r for r in bad if r["event"] == event)[field] = wrong
            self.assertFalse(inspect_stage49(bad, 56)[0])
        self.assertFalse(inspect_stage49(
            [r for r in baseline if r["event"] != 0x5600], 56)[0])

    def test_stage55_exact_root_kernel_and_checkpoint(self):
        baseline = sample(physical=True, written=True, stage=55)
        self.assertTrue(inspect_stage49(baseline, 55)[0])
        for event, field, wrong in (
            (0x5500, "c", 0xED5123CEE5377846),
            (0x4802, "a", 0x81AC30D8),
            (0x4802, "b", 0xD0FFB5A8),
            (0x2800, "a", 0x361846AAB01F8040),
        ):
            bad = sample(physical=True, written=True, stage=55)
            next(r for r in bad if r["event"] == event)[field] = wrong
            self.assertFalse(inspect_stage49(bad, 55)[0])
        self.assertFalse(inspect_stage49(
            [r for r in baseline if r["event"] != 0x5500], 55)[0])

    def test_stage54_exact_kernel_and_checkpoint(self):
        baseline = sample(physical=True, written=True, stage=54)
        self.assertTrue(inspect_stage49(baseline, 54)[0])
        for event, field, wrong in (
            (0x5400, "c", 0x361846AAB01F8040),
            (0x4802, "a", 0x81AC2F88),
            (0x4802, "b", 0xD0FFB5A8),
            (0x2800, "a", 0x945E61817C333218),
        ):
            corrupt = sample(physical=True, written=True, stage=54)
            next(r for r in corrupt if r["event"] == event)[field] = wrong
            self.assertFalse(inspect_stage49(corrupt, 54)[0])
        incomplete = [r for r in baseline if r["event"] != 0x5400]
        self.assertFalse(inspect_stage49(incomplete, 54)[0])

    def test_stage53_exact_kernel_preflight_and_checkpoint(self):
        baseline = sample(physical=True, written=True, stage=53)
        self.assertTrue(inspect_stage49(baseline, 53)[0])
        for event, field, wrong in (
            (0x5300, "c", 0x945E61817C333218),
            (0x4802, "a", 0x81AC3C88),
            (0x4802, "b", 0xB0FFB5A8),
            (0x2800, "a", 0x40F672D3500699B6),
        ):
            bad = sample(physical=True, written=True, stage=53)
            next(r for r in bad if r["event"] == event)[field] = wrong
            self.assertFalse(inspect_stage49(bad, 53)[0])
        self.assertFalse(inspect_stage49(
            [r for r in baseline if r["event"] != 0x5300], 53)[0])

    def test_stage52_requires_matching_rebuilt_kernel_and_console(self):
        base = sample(physical=True, written=True, stage=52)
        self.assertTrue(inspect_stage49(base, 52)[0])
        for ev, field, value in (
            (0x5200, "c", 0), (0x4802, "b", 0x90FFB5C8),
            (0x2800, "a", 0x40F672D3500699B6),
        ):
            broken = sample(physical=True, written=True, stage=52)
            next(item for item in broken if item["event"] == ev)[field] = value
            self.assertFalse(inspect_stage49(broken, 52)[0])
        self.assertFalse(inspect_stage49(
            [r for r in base if r["event"] != 0x5200], 52)[0])

    def test_stage51_needs_payload_handoff_marker(self):
        good, _ = inspect_stage49(sample(physical=True, written=True, stage=51), 51)
        self.assertTrue(good)
        incomplete = [r for r in sample(physical=True, written=True, stage=51)
                      if r["event"] != 0x5100]
        self.assertFalse(inspect_stage49(incomplete, 51)[0])
        incorrect = sample(physical=True, written=True, stage=51)
        next(item for item in incorrect if item["event"] == 0x4802)["a"] = 0x81AC0C68
        self.assertFalse(inspect_stage49(incorrect, 51)[0])
        old_kernel = sample(physical=True, written=True, stage=51)
        next(item for item in old_kernel if item["event"] == 0x2800)["a"] = 0x1A0CF300CD5A6F86
        self.assertFalse(inspect_stage49(old_kernel, 51)[0])

    def test_unsafe_m4u_mode_skip_is_verified_without_pixel_claim(self):
        good, msg = inspect_stage49(sample())
        self.assertTrue(good)
        self.assertIn("safely skipped", msg)

    def test_physical_mode_pixel_readback_requires_exact_words(self):
        good, msg = inspect_stage49(sample(physical=True, written=True))
        self.assertTrue(good)
        self.assertIn("pixels written", msg)
        damaged = sample(physical=True, written=True)
        next(r for r in damaged if r["event"] == 0x4902)["c"] = 0
        self.assertFalse(inspect_stage49(damaged)[0])

    def test_missing_or_unjustified_write_never_passes(self):
        self.assertFalse(inspect_stage49(sample(physical=True))[0])
        self.assertFalse(inspect_stage49(sample(written=True))[0])
        truncated = sample()[:-1]
        self.assertFalse(inspect_stage49(truncated)[0])

    def test_stage50_requires_live_video_bootargs_redirect(self):
        good, msg = inspect_stage49(
            sample(physical=True, written=True, stage=50), 50)
        self.assertTrue(good)
        self.assertIn("redirected", msg)
        data = sample(physical=True, written=True, stage=50)
        next(r for r in data if r["event"] == 0x5000)["b"] = 0x5E605000
        self.assertFalse(inspect_stage49(data, 50)[0])
        data = sample(physical=True, written=True, stage=50)
        data = [r for r in data if r["event"] != 0x5000]
        self.assertFalse(inspect_stage49(data, 50)[0])


if __name__ == "__main__":
    unittest.main()
