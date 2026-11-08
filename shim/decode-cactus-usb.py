#!/usr/bin/env python3
"""Decode 56-byte CLOG v2 frames from a possibly partial Windows COM capture.

No dependency beyond Python 3. This parser tolerates arbitrary read
boundaries, junk, truncated frames and lost/disconnected sequences.
"""
import argparse
import collections
from pathlib import Path
import struct
import zlib

MAGIC = b"CLOG"
SIZE = 56
BODY = struct.Struct("<4sBBBBIIIQQQQI")
assert BODY.size == SIZE


def decode(raw: bytes):
    records = []
    corrupt = 0
    noise = 0
    offset = 0
    while offset + SIZE <= len(raw):
        index = raw.find(MAGIC, offset)
        if index < 0:
            break
        noise += index - offset
        if index + SIZE > len(raw):
            offset = index
            break
        frame = raw[index:index + SIZE]
        fields = BODY.unpack(frame)
        (magic, version, size, stage, el, seq, session, event,
         ticks, arg0, arg1, arg2, crc) = fields
        if version != 2 or size != SIZE or zlib.crc32(frame[:52]) != crc:
            corrupt += 1
            offset = index + 1
            continue
        records.append(dict(offset=index, stage=stage, el=el,
                            seq=seq, session=session, event=event,
                            ticks=ticks, a=arg0, b=arg1, c=arg2))
        offset = index + SIZE
    noise += len(raw) - offset
    return records, corrupt, noise


def assess(records):
    seen = set()
    duplicates = 0
    gaps = 0
    regressions = 0
    last = {}
    for rec in records:
        key = rec["session"], rec["seq"]
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        previous = last.get(rec["session"])
        if previous is not None:
            if rec["seq"] > previous + 1:
                gaps += rec["seq"] - previous - 1
            elif rec["seq"] <= previous:
                regressions += 1
        last[rec["session"]] = rec["seq"]
    return gaps, duplicates, regressions


def inspect_stage49(records, stage=49):
    """Validate guarded display evidence and optional XNU video bootargs."""
    selected = [r for r in records if r["stage"] == stage]
    by_event = {}
    for i, rec in enumerate(selected):
        by_event.setdefault(rec["event"], []).append((i, rec))

    required = (0x1900, 0x4500, 0x4700, 0x4801, 0x4802,
                0x4900, 0x4901, 0x2303, 0x2800, 0x3500, 0x3900)
    if any(len(by_event.get(ev, ())) != 1 for ev in required):
        return False, "incomplete prehandoff trace; missing or duplicated required markers"
    if any(by_event[a][0][0] >= by_event[b][0][0]
           for a, b in zip(required, required[1:])):
        return False, "out-of-order prehandoff markers"

    def event(ev):
        return by_event[ev][0][1]

    region = event(0x4801)
    original = event(0x4802)
    kernel_identity = event(0x2800)
    mmu = event(0x4900)
    guard = event(0x4901)
    wdt = event(0x3900)
    checkpoint_pa = {51: 0x81AC0C88, 52: 0x81AC3C88,
                     53: 0x81AC2F88, 54: 0x81AC30D8,
                     55: 0x81AC3138, 56: 0x81AC31E8,
                     57: 0x81AC33C8, 58: 0x81AC36F8, 59: 0x81AC37D8, 60: 0x81AC38F8,
                     61: 0x81AC3908, 62: 0x81AC3908, 63: 0x81AC3998,
                     64: 0x81AC3998, 65: 0x81AC3BB8, 66: 0x81AC3BB8,
                     67: 0x81AC3D48, 68: 0x81AC3E68, 69: 0x81AC4068, 70: 0x81AC4028, 71: 0x81AC3E88, 72: 0x81AC3E68, 73: 0x81AC3EA8, 74: 0x81AC4028, 75: 0x81AC4348, 76: 0x81AC4368, 77: 0x81AC4488, 78: 0x81ABEA6C, 79: 0x81ABEBAC}.get(stage, 0x81AC0C68)
    checkpoint_opcode = ({52: 0xB0FFB5A8,
                          53: 0xD0FFB5A8, 54: 0xB0FFB5A8,
                          55: 0xB0FFB5A8, 56: 0xB0FFB5A8,
                          57: 0xB0FFB5A8, 58: 0xB0FFB5A8, 59: 0xB0FFB5A8, 60: 0xB0FFB5A8,
                          61: 0xB0FFB5A8, 62: 0xB0FFB5A8, 63: 0xB0FFB5A8,
                          64: 0xB0FFB5A8, 65: 0xB0FFB5A8, 66: 0xB0FFB5A8,
                          67: 0xB0FFB5A8, 68: 0xB0FFB5A8, 69: 0x90FFB5A8, 70: 0x90FFB5A8, 71: 0xB0FFB5A8, 72: 0xB0FFB5A8, 73: 0xB0FFB5A8, 74: 0x90FFB5A8, 75: 0x90FFB5A8, 76: 0x90FFB5A8, 77: 0x90FFB5A8, 78: 0xF9400108, 79: 0xF9400108}.get(stage, 0x90FFB5C8))
    kernel_markers = {51: 0x40F672D3500699B6, 52: 0x945E61817C333218,
                      53: 0x361846AAB01F8040, 54: 0xED5123CEE5377846,
                      55: 0xEA16FAA6D49EB135, 56: 0x3004D4478977B6B2,
                      57: 0x7A0B778D113B3A66, 58: 0x9D6977D4F44B9216,
                      59: 0xED3074CC9E889F88, 60: 0x2F3B02C004763C7A,
                      61: 0x15FDBDAB0AA0CB1F, 62: 0x15FDBDAB0AA0CB1F,
                      63: 0xC9B059C9DAD73F49, 64: 0xC9B059C9DAD73F49,
                      65: 0x8B9D47E456C92F59, 66: 0x9F76552002E5BA8F,
                      67: 0x5FDE9842617A904D, 68: 0xDF201510EDFDA5E2, 69: 0xC2A15E3BCCA44E1A, 70: 0xC9645C067882397D, 71: 0xEAD2AC800BAC9452, 72: 0x3B1AE5E7F1BA8C76, 73: 0xD5063F7F09BB5A51, 74: 0x611FC800ACD2B829, 75: 0xFD4D640BC716F1A7, 76: 0x7316640649E655D6, 77: 0x60D31B08A485278C, 78: 0x1779340D044523AD, 79: 0xA0D33E9F8C73E9B4}
    if stage in kernel_markers and kernel_identity["a"] != kernel_markers[stage]:
        return False, f"Stage{stage} trace did not identify the rebuilt XNU kernel"
    if stage in (62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79):
        # Read-only physical identity snapshot, recorded before the risky
        # native pe_init_fiq() mapping. Missing frames are an incomplete
        # capture, not evidence of zero-valued hardware registers.
        begin, end = by_event.get(0x6200, []), by_event.get(0x6202, [])
        frames = by_event.get(0x6201, [])
        if not (len(begin) == len(end) == 1 and frames and
                by_event[0x1900][0][0] < begin[0][0] < frames[0][0] and
                frames[-1][0] < end[0][0] < by_event[0x4500][0][0] and
                (end[0][1]["a"], end[0][1]["b"], end[0][1]["c"]) ==
                (0x01000000, 0x0B100000, 0x0C100000)):
            return False, "Stage62 physical GICR census markers missing or invalid"
        expected = 0x0C100000
        for _, frame in frames:
            if frame["a"] != expected:
                return False, "Stage62 noncontiguous GICR redistributor frames"
            expected += 0x20000
        if len(frames) > 16:
            return False, "Stage62 GICR census exceeded declared MMIO region"
    if not (region["b"] == 0x7F0D0000 and
            region["c"] == 0xE20000 and (region["a"] & 3) == 3 and
            original["a"] == checkpoint_pa and
            original["b"] == checkpoint_opcode and original["c"] == 1 and
            mmu["a"] == 0x14003380 and
            mmu["c"] == int((mmu["b"] & 1) == 0) and
            (wdt["b"] & 1) == 0):
        return False, "carveout, original XNU instruction, SMI mode or WDT inconsistent"
    if guard["a"] not in (0, 1) or guard["b"] not in (0, 1):
        return False, "malformed framebuffer safety result"
    if guard["a"] == 1:
        written = by_event.get(0x4902, [])
        if not (mmu["c"] == 1 and guard["b"] == 1 and
                len(written) == 1 and
                by_event[0x4901][0][0] < written[0][0] <
                by_event[0x2303][0][0] and
                written[0][1]["a"] == 0xFF00FF00 and
                written[0][1]["b"] == 0xFFFF00FF and
                written[0][1]["c"] == 1):
            return False, "guard allowed framebuffer test but readback failed"
        if stage in (50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79):
            redirect = by_event.get(0x5000, [])
            if not (len(redirect) == 1 and
                    by_event[0x4902][0][0] < redirect[0][0] <
                    by_event[0x2303][0][0] and
                    (redirect[0][1]["a"],
                     redirect[0][1]["b"],
                     redirect[0][1]["c"]) ==
                    (0x5E605000, 0x7F4DB000, 1)):
                return False, "XNU Video boot-args redirection missing or incorrect"
            if stage in (51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79):
                console = by_event.get(0x5100, [])
                if not (len(console) == 1 and
                        redirect[0][0] < console[0][0] <
                        by_event[0x2303][0][0] and
                        console[0][1]["a"] == 0x7F4DB000 and
                        console[0][1]["b"] != 0 and
                        44 <= console[0][1]["c"] <= 65536):
                    return False, "Stage51 console payload prehandoff marker missing"
                if stage in (52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79):
                    tag = {52: 0x5200, 53: 0x5300, 54: 0x5400,
                           55: 0x5500, 56: 0x5600, 57: 0x5700,
                           58: 0x5800, 59: 0x5900, 60: 0x6000, 61: 0x6100,
                           62: 0x6100, 63: 0x6100, 64: 0x6100, 65: 0x6100,
                           66: 0x6100, 67: 0x6100, 68: 0x6100, 69: 0x6100, 70: 0x6100, 71: 0x6100, 72: 0x6100, 73: 0x6100, 74: 0x6100, 75: 0x6100, 76: 0x6100, 77: 0x6100, 78: 0x6100, 79: 0x6100}[stage]
                    expected_entry = 0x81430488 if stage == 52 else 0x8142D488
                    diag = by_event.get(tag, [])
                    if not (len(diag) == 1 and
                            console[0][0] < diag[0][0] <
                            by_event[0x2303][0][0] and
                            (diag[0][1]["a"], diag[0][1]["b"], diag[0][1]["c"]) ==
                            (0x7F4DB000, expected_entry,
                             0x15FDBDAB0AA0CB1F if stage >= 63 else kernel_markers[stage])):
                        return False, f"Stage{stage} native-console prehandoff marker missing"
                    return True, f"Stage{stage} rebuilt XNU / live framebuffer prehandoff passed; inspect screen for native progress"
                return True, "Stage51 live layer1 / ADT handoff preflight passed; native XNU logs unconfirmed"
            return True, "XNU Video boot-args redirected to live OVL layer1, readback passed"
        return True, "guarded layer-1 pixels written and read back; check screen visibility separately"
    if 0x4902 in by_event or (stage in (50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79) and
                              any(e in by_event for e in (0x5000, 0x5100, 0x5200, 0x5300, 0x5400, 0x5500, 0x5600, 0x5700, 0x5800, 0x5900, 0x6000, 0x6100))):
        return False, "unsafe framebuffer write marker despite guard rejection"
    return True, ("framebuffer write safely skipped "
                  f"(OVL MMU register={mmu['b']:#x}, "
                  f"reserved carveout match={guard['b']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--require-stage14", action="store_true",
                        help="fail if no useful Stage 14 hardware evidence")
    parser.add_argument("--require-stage15", action="store_true",
                        help="require Stage 15 shim entry, FDT, and layout checkpoints")
    parser.add_argument("--require-stage15-early", action="store_true",
                        help="require early real-shim USB entry and stream checkpoints")
    parser.add_argument("--require-stage16", action="store_true",
                        help="require Stage 16 real shim FDT/debug checkpoints and DONE")
    parser.add_argument("--require-stage17", action="store_true",
                        help="require Stage 17 live FDT memory map and completion")
    parser.add_argument("--require-stage18", action="store_true",
                        help="require real payload admission, layout READY and DONE")
    parser.add_argument("--require-stage20", action="store_true",
                        help="require 10 segments copied and EL1 ERET/HVC return")
    parser.add_argument("--require-stage20b", action="store_true",
                        help="require proof that XNU's first B reached its patched BRK target")
    parser.add_argument("--require-stage20c", action="store_true",
                        help="require early XNU framebuffer path and pre-VBAR breakpoint")
    parser.add_argument("--require-stage20d", action="store_true",
                        help="require real XNU VBAR handoff and post-VBAR EL1h exception")
    parser.add_argument("--require-stage21c1", action="store_true",
                        help="require pre-MMU EL1t trap, tables/sysregs and EL2 return")
    parser.add_argument("--require-stage21c2", action="store_true",
                        help="require post-MMU EL1t trap via translated vector and EL2 return")
    parser.add_argument("--require-stage21d", action="store_true",
                        help="require high-VA C checkpoint or captured exception and clean EL2 recovery")
    parser.add_argument("--require-stage22", action="store_true",
                        help="require Stage27 CPU/timer/memory snapshots and deeper XNU C checkpoint or captured fault")
    parser.add_argument("--require-stage23", action="store_true",
                        help="require Stage28 framebuffer preflight, native XNU entry, and genuine fault/held COM25 capture")
    parser.add_argument("--require-stage24", action="store_true",
                        help="require Stage29 native XNU exception plus pre-EL2-clobber register context")
    parser.add_argument("--require-stage25", action="store_true",
                        help="require Stage30 null-PTE checkpoint, exact VA/PA range and safe page-table descriptor report")
    parser.add_argument("--require-stage26", action="store_true",
                        help="require Stage31 framebuffer-height bridge, native EL1 continuation and original register fault capture")
    parser.add_argument("--require-stage28", action="store_true",
                        help="require rebuilt-XNU Stage33 exact null-PTE request, descriptor walk and safe restoration")
    parser.add_argument("--require-stage35", action="store_true",
                        help="classify Stage35 host-delivered handoff markers separately from native XNU EL1 entry")
    parser.add_argument("--require-combined-stage", type=int, choices=(45, 47),
                        help="require a clean dual-display/XNU native checkpoint from Stage45 or Stage47")
    parser.add_argument("--require-stage49", action="store_true",
                        help="validate Stage49 prehandoff and framebuffer safety, without requiring EL1 output")
    parser.add_argument("--require-stage50", action="store_true",
                        help="validate guarded Stage50 live-LK framebuffer handoff to XNU boot_args")
    parser.add_argument("--require-stage51", action="store_true",
                        help="validate Stage51 on-panel framebuffer and rebuilt ADT prehandoff markers")
    parser.add_argument("--require-stage52", action="store_true",
                        help="validate Stage52 framebuffer and rebuilt native-console prehandoff markers")
    parser.add_argument("--require-stage53", action="store_true",
                        help="validate Stage53 smaller-font Cactarwin console and XNU kernel prehandoff markers")
    parser.add_argument("--require-stage54", action="store_true",
                        help="validate Stage54 exact IOKit/BSD checkpoint kernel and framebuffer prehandoff")
    parser.add_argument("--require-stage55", action="store_true",
                        help="validate Stage55 exact BSD gate + diagnostic RAMDisk kernel prehandoff")
    parser.add_argument("--require-stage56", action="store_true",
                        help="validate Stage56 CPU synchronization diagnostic prehandoff")
    parser.add_argument("--require-stage57", action="store_true",
                        help="validate Stage57 CPU0 SGI readiness and retry prehandoff")
    parser.add_argument("--require-stage58", action="store_true",
                        help="validate Stage58 GICv3 IRQ register and recovery prehandoff")
    parser.add_argument("--require-stage59", action="store_true",
                        help="validate Stage59 CPU0 IRQ-independent SGI1 recovery")
    parser.add_argument("--require-stage60", action="store_true",
                        help="validate Stage60 SGI8 GICv3 prehandoff")
    parser.add_argument("--require-stage61", action="store_true",
                        help="validate SHA-pinned Stage61 GICR identity probe prehandoff")
    parser.add_argument("--require-stage62", action="store_true",
                        help="validate Stage62 physical GICR census and pinned Stage61 XNU")
    parser.add_argument("--require-stage63", action="store_true",
                        help="validate Stage63 physical GICR census and pinned Stage63 XNU")
    parser.add_argument("--require-stage64", action="store_true",
                        help="validate Stage64 physical GICR census and corrected XNU ADT")
    parser.add_argument("--require-stage65", action="store_true",
                        help="validate Stage65 GICR census and native PID1 proof kernel")
    parser.add_argument("--require-stage66", action="store_true",
                        help="validate Stage66 GICR census and top PID1 proof indicator")
    parser.add_argument("--require-stage67", action="store_true",
                        help="validate Stage67 GICR census and native VFS checkpoints")
    parser.add_argument("--require-stage68", action="store_true",
                        help="validate Stage68 GICR census and BSD root/PID1 checkpoint kernel")
    parser.add_argument("--require-stage69", action="store_true",
                        help="validate Stage69 GICR census and BSD fine checkpoint kernel")
    parser.add_argument("--require-stage70", action="store_true",
                        help="validate Stage70 GICR census and minimal-root/PID1 kernel")
    parser.add_argument("--require-stage71", action="store_true",
                        help="validate Stage71 direct-exec and mockfs PID1 GICR kernel")
    parser.add_argument("--require-stage72", action="store_true",
                        help="validate Stage72 mockfs pathname and POSIX executable mode")
    parser.add_argument("--require-stage73", action="store_true",
                        help="validate Stage73 PID1 explicit VM map and copyout kernel")
    parser.add_argument("--require-stage74", action="store_true",
                        help="validate Stage74 wired PID1 physical page copy")
    parser.add_argument("--require-stage75", action="store_true",
                        help="validate Stage75 PID1 exec scratch read path")
    parser.add_argument("--require-stage76", action="store_true",
                        help="validate Stage76 PID1 scratch shadow read kernel")
    parser.add_argument("--require-stage77", action="store_true",
                        help="validate Stage77 PID1 wired execargs kernel")
    parser.add_argument("--require-stage78", action="store_true",
                        help="validate Stage78 mockfs and PID1 Mach-O header read tracing")
    parser.add_argument("--require-stage79", action="store_true",
                        help="validate Stage79 virtual RAMDisk vnode read fix")
    parser.add_argument("--early-level", type=int, choices=[1, 2, 3, 4, 5], default=1,
                        help="expected Stage 15 early diagnostic level")
    parser.add_argument("--show", type=int, default=15)
    args = parser.parse_args()
    raw = args.capture.read_bytes()
    records, corrupt, noise = decode(raw)
    gaps, duplicates, regressions = assess(records)
    print(f"input={len(raw)} bytes valid_frames={len(records)} "
          f"bad_frames={corrupt} unmatched_bytes={noise}")
    print(f"gaps={gaps} duplicates={duplicates} regressions={regressions} "
          f"sessions={[hex(s) for s in sorted({r['session'] for r in records})]}")
    counts = collections.Counter(r["event"] for r in records)
    print("events", {hex(e): n for e, n in sorted(counts.items())})
    for r in records[:max(0, args.show)]:
        print(f"seq={r['seq']:4d} stage={r['stage']} EL={r['el']:#x} "
              f"event={r['event']:#x} tick={r['ticks']} "
              f"a={r['a']:#x} b={r['b']:#x} c={r['c']:#x}")
    # The GICR snapshot is the main purpose of Stage62. Always show its
    # physical register values even when --show stops before these frames.
    frames = [r for r in records if r['stage'] in (62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79) and r['event'] == 0x6201]
    for r in frames:
        print(f"STAGE62_GICR physical={r['a']:#x} pidr2={r['b']:#x} "
              f"arch={(r['b'] >> 4) & 15} typer={r['c']:#x} "
              f"affinity={(r['c'] >> 32) & 0xffffffff:#x}")
    for r in records:
        if r['stage'] in (62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79) and r['event'] == 0x6200:
            print(f"STAGE62_GICD MPIDR={r['a']:#x} PIDR2={r['b'] >> 32:#x} "
                  f"TYPER={r['b'] & 0xffffffff:#x} GICR_PA={r['c']:#x}")
    if (args.require_stage49 or args.require_stage50 or args.require_stage51
            or args.require_stage52 or args.require_stage53 or args.require_stage54
            or args.require_stage55 or args.require_stage56 or args.require_stage57
            or args.require_stage58 or args.require_stage59 or args.require_stage60
            or args.require_stage61 or args.require_stage62 or args.require_stage63
            or args.require_stage64 or args.require_stage65 or args.require_stage66
            or args.require_stage67 or args.require_stage68 or args.require_stage69 or args.require_stage70 or args.require_stage71 or args.require_stage72 or args.require_stage73 or args.require_stage74 or args.require_stage75 or args.require_stage76 or args.require_stage77 or args.require_stage78 or args.require_stage79):
        stage = (56 if args.require_stage56 else (55 if args.require_stage55 else
                 (54 if args.require_stage54 else
                 (53 if args.require_stage53 else (52 if args.require_stage52 else
                  (51 if args.require_stage51 else (50 if args.require_stage50 else 49)))))))
        if args.require_stage57:
            stage = 57
        if args.require_stage58:
            stage = 58
        if args.require_stage59:
            stage = 59
        if args.require_stage60:
            stage = 60
        if args.require_stage61:
            stage = 61
        if args.require_stage62:
            stage = 62
        if args.require_stage63:
            stage = 63
        if args.require_stage64:
            stage = 64
        if args.require_stage65:
            stage = 65
        if args.require_stage66:
            stage = 66
        if args.require_stage67:
            stage = 67
        if args.require_stage68:
            stage = 68
        if args.require_stage69:
            stage = 69
        if args.require_stage70:
            stage = 70
        if args.require_stage71:
            stage = 71
        if args.require_stage72:
            stage = 72
        if args.require_stage73:
            stage = 73
        if args.require_stage74:
            stage = 74
        if args.require_stage75:
            stage = 75
        if args.require_stage76:
            stage = 76
        if args.require_stage77:
            stage = 77
        if args.require_stage78:
            stage = 78
        if args.require_stage79:
            stage = 79
        good, result = inspect_stage49(records, stage)
        no_loss = not (corrupt or noise or gaps or duplicates or regressions)
        good = good and no_loss and all(r["stage"] == stage for r in records)
        print(f"STAGE{stage} " + ("PREFLIGHT PASS: " if good else "INCOMPLETE: ") +
              (result if no_loss else "corrupt, noisy or dropped trace frames"))
        if good:
            print(f"STAGE{stage}: prehandoff delivered; post-handoff XNU progress remains unconfirmed")
        else:
            raise SystemExit(1)
    if args.require_combined_stage is not None:
        stage = args.require_combined_stage
        selected = [r for r in records if r["stage"] == stage]
        first = {}
        for i, r in enumerate(selected):
            first.setdefault(r["event"], i)
        required = [0x4500, 0x4501, 0x4502, 0x4503,
                    0x4504, 0x4505, 0x4506, 0x4507]
        if stage == 47:
            required += [0x4700, 0x4701, 0x4702, 0x4703,
                         0x4705, 0x4704, 0x4706]
        required += [0x3900, 0x20a1, 0x2206, 0x220b]
        ordered = all(e in first for e in required) and all(
            first[a] < first[b] for a, b in zip(required, required[1:]))
        def observed(event, match):
            return any(r["event"] == event and match(r) for r in selected)
        base = observed(0x4500, lambda r: r["a"] == 0x1400b000)
        rdma = observed(0x4504, lambda r: r["a"] == 0x1400d000)
        watchdog = observed(0x3900, lambda r: (r["b"] & 1) == 0)
        entry = observed(0x20a1, lambda r:
                         r["el"] == 4 and
                         (r["a"], r["b"], r["c"]) ==
                         (4, 0x8142d488, 0x824bc000))
        checkpoint = (0xe43, 0xfffffff007ac0c64) if stage == 45 else (
            0xe44, 0xfffffff007ac0c68)
        trapped = observed(0x2206, lambda r:
                           r["a"] == 0xf2000000 + checkpoint[0] and
                           r["b"] == checkpoint[1])
        restored = observed(0x220b, lambda r:
                            (r["a"], r["b"], r["c"]) == (1, 1, 1))
        tag = observed(0x2407, lambda r: r["c"] == stage)
        complete = (ordered and base and rdma and watchdog and entry and
                    trapped and restored and tag and
                    len(selected) == len(records) and
                    not (corrupt or noise or gaps or duplicates or regressions))
        print(f"STAGE{stage} COMBINED " +
              ("NATIVE XNU + DISPLAY REGISTERS PASS" if complete else
               f"INCOMPLETE: missing={[hex(e) for e in required if e not in first]} "
               f"ordered={ordered} ovl={base} rdma={rdma} "
               f"wdt={watchdog} el1={entry} brk={trapped} "
               f"restore={restored} stage_id={tag}"))
        if not complete:
            raise SystemExit(1)
    # Deliberately demand a *changing* event stream, not a repeated
    # 32-byte Stage 12 marker, with consistent order and CRC.
    unique_sequences = len({(r["session"], r["seq"]) for r in records})
    valid = (len(records) >= 20 and unique_sequences >= 20 and
             any(r["event"] == 0x1403 for r in records) and
             all(r["stage"] == 14 for r in records) and
             not duplicates and not regressions and not corrupt)
    if args.require_stage14:
        print("STAGE14 " + ("PASS" if valid else "NOT VERIFIED"))
        if not valid:
            raise SystemExit(1)
    if args.require_stage15:
        events = {r["event"] for r in records if r["stage"] == 15}
        needed = {0x1500, 0x1501, 0x1502, 0x1503, 0x1504, 0x15ff}
        passed = (needed <= events and not corrupt and
                  not duplicates and not regressions and
                  all(r["stage"] == 15 for r in records))
        print("STAGE15 " + ("PREFLIGHT PASS" if passed else
                            f"NOT VERIFIED; missing={sorted(needed - events)}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage15_early:
        event_set = {r["event"] for r in records if r["stage"] == 15}
        required = {0x1580, 0x1581, 0x1582, 0x158a}
        if args.early_level >= 2:
            required |= {0x1583, 0x1584}
        if args.early_level >= 3:
            required |= {0x1585, 0x1586}
        if args.early_level >= 4:
            required |= {0x1587, 0x1588}
        if args.early_level >= 5:
            required |= {0x158b, 0x158c}
        done = any(r["event"] == 0x158a and r["a"] == args.early_level
                   for r in records)
        reserve_summary = next((r for r in records if r["event"] == 0x158b), None)
        reserve_ranges = [r for r in records if r["event"] == 0x158c]
        reserve_count_ok = (args.early_level < 5 or
                            (reserve_summary is not None and
                             reserve_summary["a"] == len(reserve_ranges) and
                             sorted(r["a"] for r in reserve_ranges) ==
                             list(range(reserve_summary["a"]))))
        passed = (len(records) >= 12 and done and required <= event_set and
                  reserve_count_ok and
                  not corrupt and not duplicates and not regressions and
                  all(r["stage"] == 15 for r in records))
        print("STAGE15 EARLY " + ("PASS" if passed else
              f"NOT VERIFIED; missing={list(map(hex, sorted(required - event_set)))} "
              f"reservation_count_ok={reserve_count_ok}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage16:
        stage_records = [r for r in records if r["stage"] == 16]
        required = (0x1600, 0x1601, 0x1610, 0x1611, 0x1612,
                    0x1620, 0x1621, 0x16ff)
        first = {}
        for index, record in enumerate(stage_records):
            first.setdefault(record["event"], index)
        all_present = all(event in first for event in required)
        ordered = all_present and all(first[x] < first[y]
                                      for x, y in zip(required, required[1:]))
        parse_ok = any(r["event"] == 0x1612 and r["a"] == 1
                       for r in stage_records)
        usb_ok = any(r["event"] == 0x1601 and r["a"] == 1
                     for r in stage_records)
        fault = any(r["event"] == 0x16ee for r in stage_records)
        passed = (ordered and parse_ok and usb_ok and not fault and
                  not corrupt and not duplicates and not regressions and
                  not gaps and len(stage_records) >= 8 and
                  len(stage_records) == len(records))
        print("STAGE16 " + ("PREFLIGHT PASS" if passed else
             "NOT VERIFIED; missing=" +
             str([hex(e) for e in required if e not in first]) +
             f" ordered={ordered} fdt_parsed={parse_ok} usb={usb_ok} fault={fault}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage17:
        selected = [r for r in records if r["stage"] == 17]
        needed = (0x1700, 0x1701, 0x1710, 0x1711,
                  0x1712, 0x1713, 0x1714, 0x1718, 0x17ff)
        first = {}
        for i, record in enumerate(selected):
            first.setdefault(record["event"], i)
        present = all(event in first for event in needed)
        ordered = present and all(first[a] < first[b]
                                  for a, b in zip(needed, needed[1:]))
        parsed = any(r["event"] == 0x1712 and r["a"] == 1
                     and r["b"] >= 1 for r in selected)
        header = any(r["event"] == 0x1711 and r["a"] == 1
                     for r in selected)
        connected = any(r["event"] == 0x1701 and r["a"] == 1
                        for r in selected)
        fault = any(r["event"] == 0x17ee for r in selected)
        passed = (ordered and parsed and header and connected and
                  not fault and not corrupt and not gaps and
                  not duplicates and not regressions and
                  len(selected) == len(records))
        print("STAGE17 " + ("MAP AND COMPLETION PASS" if passed else
              f"NOT VERIFIED; missing={[hex(e) for e in needed if e not in first]} "
              f"ordered={ordered} parsed={parsed} fault={fault}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage18:
        selected = [r for r in records if r["stage"] == 18]
        required = (0x1800, 0x1801, 0x1810, 0x1811,
                    0x1820, 0x1821, 0x1830, 0x1831,
                    0x1840, 0x18f0, 0x18ff)
        first = {}
        for i, r in enumerate(selected):
            first.setdefault(r["event"], i)
        present = all(e in first for e in required)
        ordered = present and all(first[a] < first[b]
                                  for a, b in zip(required, required[1:]))
        usb = any(r["event"] == 0x1801 and r["a"] == 1 for r in selected)
        fdt = any(r["event"] == 0x1811 and r["a"] == 1 for r in selected)
        ram = any(r["event"] == 0x1821 and r["a"] == 1 for r in selected)
        verdicts = [r["a"] for r in selected if r["event"] == 0x1831]
        done = any(r["event"] == 0x18ff and r["a"] == 0 for r in selected)
        ready = any(r["event"] == 0x18f0 and r["a"] and r["b"]
                    for r in selected)
        fault = any(r["event"] == 0x18ee for r in selected)
        segments = sum(r["event"] == 0x1840 for r in selected)
        claimed_segments = next((r["c"] for r in selected
                                 if r["event"] == 0x1820), 0)
        passed = (ordered and usb and fdt and ram and verdicts == [0]
                  and done and ready and not fault and
                  0 < claimed_segments <= 64 and segments == claimed_segments and
                  not corrupt and not gaps and not duplicates and
                  not regressions and len(selected) == len(records))
        print("STAGE18 " + ("PAYLOAD ADMISSION PASS" if passed else
              f"NOT VERIFIED; missing={[hex(e) for e in required if e not in first]} "
              f"ordered={ordered} usb={usb} fdt={fdt} ram={ram} "
              f"verdicts={verdicts} segments={segments}/{claimed_segments} "
              f"ready={ready} done={done} fault={fault}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage20:
        selected = [r for r in records if r["stage"] == 20]
        first = {}
        for i, r in enumerate(selected):
            first.setdefault(r["event"], i)
        required = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911,
                    0x1930, 0x1940, 0x1941, 0x1950, 0x1951,
                    0x1952, 0x20a0, 0x20a1, 0x20a2, 0x20a3,
                    0x20ff, 0x19ff)
        present = all(e in first for e in required)
        ordered = present and all(first[a] < first[b]
                                  for a, b in zip(required, required[1:]))
        starts = [r["a"] for r in selected if r["event"] == 0x1940]
        finishes = [r["a"] for r in selected if r["event"] == 0x1941]
        ten = starts == list(range(10)) and finishes == list(range(10))
        fdt = any(r["event"] == 0x1910 and r["a"] == 1 for r in selected)
        accepted = any(r["event"] == 0x1911 and r["a"] == 0 for r in selected)
        usb = any(r["event"] == 0x1901 and r["a"] == 1 for r in selected)
        at_el1 = any(r["event"] == 0x20a1 and r["el"] == 4
                     and r["a"] == 4 and r["b"] == 0x8142d488
                     and r["c"] == 0x824bc000 for r in selected)
        hvc = any(r["event"] == 0x20a2 and r["el"] == 8
                  and (r["a"] >> 26) & 0x3f == 0x16
                  and (r["a"] & 0xffff) == 0x20
                  and (r["c"] & 0xf) == 5 for r in selected)
        returned = any(r["event"] == 0x20a3 and r["el"] == 8
                       and r["a"] == 8 for r in selected)
        done = all(any(r["event"] == e and r["a"] == 0 for r in selected)
                   for e in (0x20ff, 0x19ff))
        passed = (present and ordered and ten and usb and fdt and accepted
                  and at_el1 and hvc and returned and done
                  and not any(r["event"] == 0x19ee for r in selected)
                  and not corrupt and not noise and not gaps
                  and not duplicates and not regressions
                  and len(selected) == len(records))
        print("STAGE20 " + ("EL1 ERET/HVC RETURN PASS" if passed else
              f"NOT VERIFIED: present={present} ordered={ordered} "
              f"segments={len(starts)}/{len(finishes)} ten={ten} "
              f"EL1={at_el1} HVC={hvc} returned={returned} "
              f"done={done} usb={usb} fdt={fdt} accepted={accepted}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage20b:
        selected = [r for r in records if r["stage"] == 21]
        first = {}
        for index, item in enumerate(selected):
            first.setdefault(item["event"], index)
        expected = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911, 0x1930,
                    0x1940, 0x1941, 0x1950, 0x1951, 0x1952, 0x20b0,
                    0x20a0, 0x20a1, 0x20b2, 0x20b3, 0x20a3, 0x20b4,
                    0x20ff, 0x19ff)
        present = all(e in first for e in expected)
        ordered = present and all(first[a] < first[b]
                                  for a, b in zip(expected, expected[1:]))
        starts = [r["a"] for r in selected if r["event"] == 0x1940]
        finishes = [r["a"] for r in selected if r["event"] == 0x1941]
        ten = starts == list(range(10)) and finishes == list(range(10))
        usb = any(r["event"] == 0x1901 and r["a"] == 1 for r in selected)
        fdt = any(r["event"] == 0x1910 and r["a"] == 1 for r in selected)
        admitted = any(r["event"] == 0x1911 and r["a"] == 0 for r in selected)
        entry = any(r["event"] == 0x20b0 and r["a"] == 0x8142d488
                    and r["b"] == 0x8142f0ec and r["c"] == 0x14000719
                    and r["el"] == 8 for r in selected)
        el1 = any(r["event"] == 0x20a1 and r["el"] == 4
                  and r["a"] == 4 and r["b"] == 0x8142d488
                  and r["c"] == 0x824bc000 for r in selected)
        trap = any(r["event"] == 0x20b2 and r["el"] == 4
                   and r["a"] >> 26 == 0x3c
                   and r["a"] & 0xffff == 0xb20
                   and r["b"] == 0x8142f0ec for r in selected)
        hvc = any(r["event"] == 0x20b3 and r["el"] == 8
                  and r["a"] >> 26 == 0x16
                  and r["a"] & 0xffff == 0x21
                  and r["c"] & 0xf == 5 for r in selected)
        returned = any(r["event"] == 0x20a3 and r["el"] == 8
                       and r["a"] == 8 for r in selected)
        restored = any(r["event"] == 0x20b4 and
                       (r["a"], r["b"], r["c"]) == (1, 1, 1)
                       for r in selected)
        done = all(any(r["event"] == e and r["a"] == 0 for r in selected)
                   for e in (0x20ff, 0x19ff))
        passed = (ordered and ten and usb and fdt and admitted and entry
                  and el1 and trap and hvc and returned and restored and done
                  and not any(r["event"] == 0x19ee for r in selected)
                  and not (corrupt or noise or gaps or duplicates or regressions)
                  and len(selected) == len(records))
        print("STAGE20-B " + ("FIRST REAL XNU BRANCH PASS" if passed else
              f"NOT VERIFIED; missing={[hex(e) for e in expected if e not in first]} "
              f"ordered={ordered} segments={ten} usb={usb} fdt={fdt} "
              f"admitted={admitted} entry={entry} el1={el1} trap={trap} "
              f"hvc={hvc} returned={returned} restored={restored} done={done}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage20c:
        selected = [r for r in records if r["stage"] == 22]
        events = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911, 0x1930,
                  0x1940, 0x1941, 0x1950, 0x1951, 0x1952, 0x20c0,
                  0x20a0, 0x20a1, 0x20c1, 0x20c2, 0x20b3, 0x20a3,
                  0x20c3, 0x20ff, 0x19ff)
        first = {}
        for index, rec in enumerate(selected):
            first.setdefault(rec["event"], index)
        ordered = all(e in first for e in events) and all(
            first[a] < first[b] for a, b in zip(events, events[1:]))
        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        connected = any(r["event"] == 0x1901 and r["a"] == 1 for r in selected)
        fdt = any(r["event"] == 0x1910 and r["a"] == 1 for r in selected)
        admitted = any(r["event"] == 0x1911 and r["a"] == 0 for r in selected)
        armed = any(r["event"] == 0x20c0 and r["el"] == 8
                    and (r["a"], r["b"], r["c"])
                    == (0x8142d488, 0x8142f144, 0x14000719)
                    for r in selected)
        enter = any(r["event"] == 0x20a1 and r["el"] == 4
                    and (r["a"], r["b"], r["c"])
                    == (4, 0x8142d488, 0x824bc000) for r in selected)
        breakpoint = any(r["event"] == 0x20c1 and r["el"] == 4
                         and (r["a"] >> 26) == 0x3c
                         and (r["a"] & 0xffff) == 0xc20
                         and r["b"] == 0x8142f144 for r in selected)
        fb = any(r["event"] == 0x20c2 and r["el"] == 4
                 and (r["a"], r["b"], r["c"])
                 == (0x824bc000, 0xffffffff, 0xffffffff)
                 for r in selected)
        hvc = any(r["event"] == 0x20b3 and r["el"] == 8
                  and (r["a"] >> 26) == 0x16 and
                  (r["a"] & 0xffff) == 0x21 and
                  (r["c"] & 0xf) == 5 for r in selected)
        el2 = any(r["event"] == 0x20a3 and r["el"] == 8 and r["a"] == 8
                  for r in selected)
        restored = any(r["event"] == 0x20c3 and
                       (r["a"], r["b"], r["c"]) == (1, 1, 1)
                       for r in selected)
        done = all(any(r["event"] == event and r["a"] == 0
                       for r in selected) for event in (0x20ff, 0x19ff))
        passed = (ordered and copies and connected and fdt and admitted
                  and armed and enter and breakpoint and fb and hvc and el2
                  and restored and done
                  and not any(r["event"] == 0x19ee for r in selected)
                  and not (corrupt or noise or gaps or duplicates or regressions)
                  and len(selected) == len(records))
        print("STAGE20-C " + ("EARLY XNU FRAMEBUFFER/VBAR GATE PASS"
              if passed else
              f"NOT VERIFIED ordered={ordered} copies={copies} "
              f"usb={connected} fdt={fdt} admitted={admitted} "
              f"armed={armed} EL1={enter} BRK={breakpoint} fb={fb} "
              f"hvc={hvc} EL2={el2} restore={restored} done={done}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage20d:
        selected = [r for r in records if r["stage"] == 23]
        expected = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911, 0x1930,
                    0x1940, 0x1941, 0x1950, 0x1951, 0x1952,
                    0x20d6, 0x20d0, 0x20a0, 0x20a1, 0x20d1,
                    0x20d2, 0x20d3, 0x20c2, 0x20b3, 0x20a3,
                    0x20d5, 0x20ff, 0x19ff)
        first = {}
        for index, rec in enumerate(selected):
            first.setdefault(rec["event"], index)
        ordered = all(e in first for e in expected) and all(
            first[a] < first[b] for a, b in zip(expected, expected[1:]))
        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        connected = any(r["event"] == 0x1901 and r["a"] == 1 for r in selected)
        fdt = any(r["event"] == 0x1910 and r["a"] == 1 for r in selected)
        admitted = any(r["event"] == 0x1911 and r["a"] == 0 for r in selected)
        vector = any(r["event"] == 0x20d6 and r["el"] == 8
                     and r["a"] == 0x8142e000 and r["b"] == 0x8142e200
                     and r["c"] != 0 and r["c"] % 4 == 0
                     for r in selected)
        arm = any(r["event"] == 0x20d0 and r["el"] == 8
                  and (r["a"], r["b"], r["c"])
                  == (0x8142d488, 0x8142f154, 0x14000719)
                  for r in selected)
        entry = any(r["event"] == 0x20a1 and r["el"] == 4
                    and (r["a"], r["b"], r["c"])
                    == (4, 0x8142d488, 0x824bc000) for r in selected)
        trap = any(r["event"] == 0x20d1 and r["el"] == 4
                   and r["a"] >> 26 == 0x3c and r["a"] & 0xffff == 0xd20
                   and r["b"] == 0x8142f154 for r in selected)
        vbar = any(r["event"] == 0x20d2 and r["el"] == 4
                   and (r["a"], r["b"], r["c"])
                   == (0x8142e000, 0x824bc000, 0xfffffff006000000)
                   for r in selected)
        memory = any(r["event"] == 0x20d3 and r["el"] == 4
                     and (r["a"], r["b"], r["c"])
                     == (0x80000000, 0x1e000000, 0x1e000000)
                     for r in selected)
        pixels = any(r["event"] == 0x20c2 and r["el"] == 4
                     and (r["a"], r["b"], r["c"])
                     == (0x824bc000, 0xffffffff, 0xffffffff)
                     for r in selected)
        hvc = any(r["event"] == 0x20b3 and r["el"] == 8
                  and r["a"] >> 26 == 0x16 and r["a"] & 0xffff == 0x21
                  and r["c"] & 0xf == 5 for r in selected)
        returned = any(r["event"] == 0x20a3 and r["el"] == 8
                       and r["a"] == 8 for r in selected)
        restored = any(r["event"] == 0x20d5 and
                       (r["a"], r["b"], r["c"]) == (1, 1, 1)
                       for r in selected)
        done = all(any(r["event"] == event and r["a"] == 0
                       for r in selected) for event in (0x20ff, 0x19ff))
        passed = (ordered and copies and connected and fdt and admitted
                  and vector and arm and entry and trap and vbar and memory
                  and pixels and hvc and returned and restored and done
                  and not any(r["event"] == 0x19ee for r in selected)
                  and not (corrupt or noise or gaps or duplicates or regressions)
                  and len(selected) == len(records))
        print("STAGE20-D " + ("POST-VBAR EL1h VECTOR PASS" if passed else
              f"NOT VERIFIED ordered={ordered} copies={copies} "
              f"usb={connected} fdt={fdt} admission={admitted} "
              f"vector={vector} armed={arm} EL1={entry} trap={trap} "
              f"vbar={vbar} bootargs={memory} pixels={pixels} "
              f"hvc={hvc} returned={returned} restored={restored} done={done}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage35:
        selected = [r for r in records if r["stage"] == 35]
        first = {}
        for i, rec in enumerate(selected):
            first.setdefault(rec["event"], (i, rec))
        markers = (0x1900, 0x1901, 0x1952, 0x2301, 0x2302,
                   0x2303, 0x2800, 0x3500)
        ordered = (all(e in first for e in markers) and
                   all(first[a][0] < first[b][0]
                       for a, b in zip(markers, markers[1:])))
        provenance = (0x2800 in first and
                      (first[0x2800][1]["a"],
                       first[0x2800][1]["b"],
                       first[0x2800][1]["c"]) ==
                      (0x1a0cf300cd5a6f86, 0x8142d488, 0x824bc000))
        clean = (bool(selected) and len(selected) == len(records) and
                 not any((corrupt, noise, gaps, duplicates, regressions)) and
                 0x35ee not in first)
        if not (ordered and provenance and clean):
            print("STAGE35 NOT VERIFIED: clean=", clean,
                  "ordered=", ordered, "provenance=", provenance,
                  "last=", hex(selected[-1]["event"]) if selected else "none")
            raise SystemExit(1)
        if 0x20a1 not in first:
            print("STAGE35 HANDOFF MARKERS DELIVERED TO HOST;"
                  " NATIVE XNU EXECUTION UNCONFIRMED")
            raise SystemExit(2)
        native = first[0x20a1][1]
        if not (first[0x3500][0] < first[0x20a1][0] and
                native["el"] == 4 and native["a"] == 4 and
                native["b"] == 0x8142d488 and
                native["c"] == 0x824bc000):
            print("STAGE35 EL1 ENTRY INCONSISTENT")
            raise SystemExit(1)
        print("STAGE35 NATIVE XNU EL1 ENTRY CONFIRMED;"
              " check subsequent exception and progress records")
    if args.require_stage25 or args.require_stage28:
        rebuilt = args.require_stage28
        expected_stage = 33 if rebuilt else 30
        selected = [r for r in records if r["stage"] == expected_stage]
        events = {}
        for i, rec in enumerate(selected):
            events.setdefault(rec["event"], []).append((i, rec))

        def present(event, predicate=lambda r: True):
            return len(events.get(event, [])) == 1 and predicate(events[event][0][1])

        order = (0x1900, 0x1901, 0x2203, 0x2204, 0x2300,
                 0x2500, 0x20a0, 0x2200, 0x2201, 0x2202,
                 0x2301, 0x2302, 0x2303,
                 *((0x2700,) if rebuilt else ()),
                 0x20a1, 0x2206,
                 0x2400, 0x2401, 0x2402, 0x2403, 0x2404,
                 0x2405, 0x2406, 0x2407, 0x2501, 0x2502,
                 0x2503, 0x2504, 0x2507, 0x241f, 0x2207,
                 0x2208, 0x2209, 0x220a, 0x20b3, 0x20a3,
                 0x2508, 0x220b, 0x2308, 0x20ff, 0x19ff)
        ordered = (all(e in events for e in order) and
                   all(events[a][0][0] < events[b][0][0]
                       for a, b in zip(order, order[1:])))
        clean = (len(selected) == len(records) and not
                 (corrupt or noise or gaps or duplicates or regressions))
        breakpoint = (present(0x2500, lambda r:
                      (r["a"], r["b"], r["c"]) ==
                      (0x81405218, 0xfffffff007405218, 0x941ae25e)) and
                      present(0x2206, lambda r:
                      r["a"] == 0xf2000e25 and r["b"] == 0xfffffff007405218) and
                      present(0x2501, lambda r:
                      (r["a"], r["b"], r["c"]) ==
                      (0xf2000e25, 0xfffffff007405218, 1)) and
                      present(0x220a, lambda r:
                      (r["a"], r["b"], r["c"]) ==
                      (3, 0xfffffff007405218, 0x3c)))
        # Exact mapping request must agree with original callee-saved regs.
        mapping = (present(0x2502) and present(0x2503) and
                   present(0x2404) and present(0x2405) and
                   events[0x2502][0][1]["a"] == events[0x2404][0][1]["a"] and
                   events[0x2502][0][1]["b"] == events[0x2405][0][1]["a"] and
                   events[0x2502][0][1]["c"] == events[0x2404][0][1]["c"] and
                   events[0x2503][0][1]["a"] == events[0x2404][0][1]["b"] and
                   events[0x2502][0][1]["a"] >= events[0x2503][0][1]["a"] and
                   events[0x2502][0][1]["b"] <= events[0x2502][0][1]["c"])
        walk = (present(0x2507, lambda r: 1 <= r["c"] <= 3) and
                present(0x2504) and present(0x2208) and
                events[0x2507][0][1]["a"] == events[0x2502][0][1]["a"] and
                events[0x2507][0][1]["b"] == events[0x2208][0][1]["b"] and
                all(present(0x2504 + level)
                    for level in range(events[0x2507][0][1]["c"])))
        original = (present(0x2407, lambda r: r["c"] == expected_stage) and
                    present(0x2508, lambda r:
                    (r["a"], r["b"], r["c"]) ==
                    (1, 0x81405218, 0x941ae25e)) and
                    present(0x220b, lambda r:
                    (r["a"], r["b"], r["c"]) == (1, 1, 1)) and
                    present(0x2308, lambda r:
                    (r["a"], r["b"], r["c"]) == (0, 1, 1)) and
                    present(0x20ff, lambda r: r["a"] == 0) and
                    present(0x19ff, lambda r: r["a"] == 0))
        provenance = (not rebuilt or
                      present(0x2700, lambda r:
                              (r["a"],r["b"],r["c"]) ==
                              (0xa1b8677a3449664f, 0x8142d488, 0x824bc000)))
        passed = ordered and clean and breakpoint and mapping and walk and original and provenance
        label = "STAGE28" if rebuilt else "STAGE25"
        print(label + " " + ("NULL-PTE REQUEST CAPTURED; COM25 HELD" if passed else
              f"NOT VERIFIED order={ordered} clean={clean} "
              f"breakpoint={breakpoint} mapping={mapping} "
              f"walk={walk} restored={original} provenance={provenance}"))
        if passed:
            fault = events[0x2502][0][1]
            state = events[0x2503][0][1]
            summary = events[0x2507][0][1]
            last = events[0x2504 + summary["c"] - 1][0][1]
            kinds = {0: "invalid descriptor", 1: "block descriptor",
                     2: "reserved descriptor", 3: "table/page descriptor"}
            print(f"{label} failing_va={fault['a']:#018x} "
                  f"initial_va={state['a']:#018x} "
                  f"phys_start={fault['b']:#018x} "
                  f"phys_end={fault['c']:#018x} "
                  f"page_walk_depth={summary['c']} "
                  f"last_slot={last['a']:#018x} "
                  f"last_descriptor={last['b']:#018x} "
                  f"({kinds[last['b']&3]})")
        if not passed:
            raise SystemExit(1)
    if args.require_stage23 or args.require_stage24 or args.require_stage26:
        selected = [r for r in records if r["stage"] ==
                    (31 if args.require_stage26 else 29 if args.require_stage24 else 28)]
        prefix = ("STAGE26" if args.require_stage26 else
                  "STAGE24" if args.require_stage24 else "STAGE23")
        by_event = {}
        for index, r in enumerate(selected):
            by_event.setdefault(r["event"], index)

        def seen(event, predicate):
            return any(r["event"] == event and predicate(r) for r in selected)

        first = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911,
                 0x1930, 0x1940, 0x1941, 0x1950, 0x1951,
                 0x1952, 0x2203, 0x2204, 0x2300, 0x20a0,
                 0x2200, 0x2201, 0x2202, 0x2205, 0x2301,
                 0x2302, 0x2303, 0x20a1)
        ordered = all(e in by_event for e in first) and all(
            by_event[a] < by_event[b] for a, b in zip(first, first[1:]))
        clean = (len(selected) == len(records) and not
                 (corrupt or noise or gaps or duplicates or regressions) and
                 not seen(0x19ee, lambda r: True) and
                 not seen(0x23ee, lambda r: True))
        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        platform = (seen(0x1901, lambda r: r["a"] == 1) and
                    seen(0x1910, lambda r: r["a"] == 1) and
                    seen(0x1911, lambda r: r["a"] == 0) and
                    seen(0x2200, lambda r: (r["a"] >> 24) == 0x41 and
                         ((r["a"] >> 4) & 0xfff) == 0xd03 and r["c"] == 8) and
                    seen(0x2201, lambda r: r["a"] == 13000000) and
                    seen(0x2202, lambda r: r["a"] == 0x80000000 and
                         r["b"] == 0x1e000000))
        vectors = seen(0x2203, lambda r:
                       (r["a"], r["b"], r["c"]) ==
                       (0x81429000, 0x81429200, 0xfffffff007429000))
        original = seen(0x2300, lambda r:
                        (r["a"], r["b"], r["c"]) ==
                        (0x81ac0c0c, 0xb0ffacc1, 0xb0ffacc1))
        splash = seen(0x2301, lambda r:
                      r["a"] == 0x5e605000 + 80*2880 + 48*4 and
                      r["b"] == 0x00ff00ff0000ff00 and
                      r["c"] == 0x0000ffff) and seen(
                      0x2302, lambda r:
                      r["a"] == (48 << 32) | 80 and
                      r["b"] == (288 << 32) | 80 and r["c"] == 1)
        handoff = seen(0x2303, lambda r:
                       (r["a"], r["b"], r["c"]) ==
                       (0x8142d488, 0x824bc000, 0xfffffff007ac0c0c))
        stage26_geometry = (not args.require_stage26 or (
            seen(0x2600, lambda r:
                 (r["a"], r["b"], r["c"]) == (1440, 640, 2880)) and
            seen(0x2601, lambda r:
                 (r["a"], r["b"], r["c"]) ==
                 (0x5e605000, 0xfffffff049dbb000, 0xfffffff04a000000)) and
            0x2600 in by_event and 0x2601 in by_event and
            by_event[0x2302] < by_event[0x2600] < by_event[0x2601] <
            by_event[0x2303] and
            not seen(0x2500, lambda r: True)))
        el1 = seen(0x20a1, lambda r:
                   r["el"] == 4 and r["a"] == 4 and
                   r["b"] == 0x8142d488 and r["c"] == 0x824bc000)
        common = (clean and ordered and copies and platform and vectors and
                  original and splash and handoff and stage26_geometry and el1)
        if not common:
            print(f"{prefix} NOT VERIFIED clean={clean} order={ordered} "
                  f"copies={copies} cpu={platform} vectors={vectors} "
                  f"target_original={original} splash_readback={splash} "
                  f"handoff={handoff} stage26_geometry={stage26_geometry} el1={el1}")
            raise SystemExit(1)

        fault_order = ((0x2206,) +
                       ((0x2400, 0x2401, 0x2402, 0x2403, 0x2404,
                         0x2405, 0x2406, 0x2407, 0x241f)
                        if args.require_stage24 or args.require_stage26
                        else ()) +
                       (0x2207, 0x2208, 0x2209, 0x220a,
                        0x20b3, 0x20a3, 0x220b, 0x2308, 0x20ff, 0x19ff))
        if not all(e in by_event for e in fault_order):
            print(f"{prefix} EL1 ENTRY OBSERVED; XNU OUTCOME UNKNOWN "
                  "(no complete synchronous-fault capture)")
            raise SystemExit(2)
        tail_ok = by_event[0x20a1] < by_event[0x2206] and all(
            by_event[a] < by_event[b] for a, b in zip(
                fault_order, fault_order[1:]))
        faults = [r for r in selected if r["event"] == 0x2206 and
                  (r["a"] >> 26) != 0x3c]
        fault = len(faults) == 1
        classification = (fault and seen(0x220a, lambda r:
                          r["a"] == 2 and r["b"] == faults[0]["b"] and
                          r["c"] == faults[0]["a"] >> 26))
        registers = (seen(0x2207, lambda r:
                     r["a"] == 0xfffffff007429000 and (r["c"] & 1)) and
                     seen(0x2209, lambda r:
                     r["a"] in (0xfffffff007429004, 0xfffffff007429204) and
                     (r["b"] & 15) == 5 and (r["c"] & 15) in (4, 5)))
        hvc = seen(0x20b3, lambda r: (r["a"] >> 26) == 0x16 and
                   (r["a"] & 0xffff) == 0x21)
        returned = seen(0x20a3, lambda r: r["el"] == 8 and r["a"] == 8)
        restored = seen(0x220b, lambda r:
                        (r["a"], r["b"], r["c"]) == (1, 1, 1))
        held = seen(0x2308, lambda r:
                    (r["a"], r["b"], r["c"]) == (0, 1, 1))
        completed = all(seen(e, lambda r: r["a"] == 0)
                        for e in (0x20ff, 0x19ff))
        register_dump = (not (args.require_stage24 or args.require_stage26) or (
            all(sum(r["event"] == e for r in selected) == 1
                for e in range(0x2400, 0x2408)) and
            seen(0x2400, lambda r: r["c"] != 0) and
            seen(0x2407, lambda r:
                 r["c"] == (31 if args.require_stage26 else 0x29)) and
            seen(0x241f, lambda r: r["c"] <= 4 and any(
                v["event"] == 0x2208 and v["b"] == r["b"]
                for v in selected))))
        passed = (tail_ok and fault and classification and registers and
                  register_dump and hvc and returned and restored and held and
                  completed)
        print(f"{prefix} " + ("GENUINE XNU FAULT CAPTURED; COM25 HELD" if
              passed else f"NOT VERIFIED fault={fault} class={classification} "
              f"registers={registers} hvc={hvc} returned={returned} "
              f"restored={restored} held={held} done={completed} "
              f"context={register_dump}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage22:
        selected = [r for r in records if r["stage"] == 27]
        required = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911,
                    0x1930, 0x1940, 0x1941, 0x1950, 0x1951,
                    0x1952, 0x2203, 0x2204, 0x20a0, 0x2200,
                    0x2201, 0x2202, 0x2205, 0x20a1, 0x2206,
                    0x2207, 0x2208, 0x2209, 0x220a, 0x20b3,
                    0x20a3, 0x220b, 0x20ff, 0x19ff)
        first = {}
        for index, rec in enumerate(selected):
            first.setdefault(rec["event"], index)
        ordered = all(e in first for e in required) and all(
            first[a] < first[b] for a, b in zip(required, required[1:]))

        def seen(event, pred):
            return any(r["event"] == event and pred(r) for r in selected)

        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        admission = (seen(0x1901, lambda r: r["a"] == 1) and
                     seen(0x1910, lambda r: r["a"] == 1) and
                     seen(0x1911, lambda r: r["a"] == 0))
        cpu = seen(0x2200, lambda r:
                   ((r["a"] >> 24) & 0xff) == 0x41 and
                   ((r["a"] >> 4) & 0xfff) == 0xd03 and r["c"] == 8)
        timer = seen(0x2201, lambda r: r["a"] == 13000000 and
                     r["b"] > 0 and r["c"] > 0)
        memory = seen(0x2202, lambda r:
                      r["a"] == 0x80000000 and r["b"] == 0x1e000000 and
                      0x824bc000 <= r["c"] <= 0x9e000000)
        vectors = seen(0x2203, lambda r:
                       (r["a"], r["b"], r["c"]) ==
                       (0x81429000, 0x81429200, 0xfffffff007429000))
        armed = seen(0x2204, lambda r:
                     (r["a"], r["b"], r["c"]) ==
                     (0x8142d488, 0x81ac0c0c, 0x14000719))
        preflight = seen(0x2205, lambda r:
                         r["a"] == 0x81ac0c0c and
                         r["b"] == 0xfffffff007ac0c0c)
        el1 = seen(0x20a1, lambda r: r["el"] == 4 and
                   (r["a"], r["b"], r["c"]) ==
                   (4, 0x8142d488, 0x824bc000))
        mmu = seen(0x2207, lambda r:
                   r["a"] == 0xfffffff007429000 and (r["c"] & 1) == 1)
        origin = seen(0x2209, lambda r:
                      r["a"] in (0xfffffff007429004, 0xfffffff007429204) and
                      (r["b"] & 0xf) == 5 and (r["c"] & 0xf) in (4, 5))
        hvc = seen(0x20b3, lambda r: (r["a"] >> 26) == 0x16 and
                   (r["a"] & 0xffff) == 0x21 and
                   r["b"] in (0xfffffff007429004, 0xfffffff007429204))
        milestone = seen(0x2206, lambda r:
                         (r["a"] >> 26) == 0x3c and
                         (r["a"] & 0xffff) == 0xe24 and
                         r["b"] == 0xfffffff007ac0c0c)
        fault = seen(0x2206, lambda r:
                     (r["a"] >> 26) != 0x3c)
        other_brk = seen(0x2206, lambda r:
                         (r["a"] >> 26) == 0x3c and
                         ((r["a"] & 0xffff) != 0xe24 or
                          r["b"] != 0xfffffff007ac0c0c))
        kind = (1 if milestone else (2 if fault else 3 if other_brk else 0))
        classified = seen(0x220a, lambda r:
                          r["a"] == kind and any(
                              e["event"] == 0x2206 and e["b"] == r["b"] and
                              (e["a"] >> 26) == r["c"] for e in selected))
        returned = seen(0x20a3, lambda r: r["el"] == 8 and r["a"] == 8)
        restored = seen(0x220b, lambda r:
                        (r["a"], r["b"], r["c"]) == (1, 1, 1))
        finished = all(seen(e, lambda r: r["a"] == 0)
                       for e in (0x20ff, 0x19ff))
        valid = (ordered and copies and admission and cpu and timer and
                 memory and vectors and armed and preflight and el1 and
                 mmu and origin and hvc and kind and classified and
                 returned and restored and finished and
                 len(selected) == len(records) and
                 not (corrupt or noise or gaps or duplicates or regressions) and
                 not any(r["event"] == 0x19ee for r in selected))
        verdict = ("DEEPER XNU C CHECKPOINT PASS" if milestone else
                   "FIRST XNU EXCEPTION CAPTURED" if fault else
                   "XNU BRK CAPTURED" if other_brk else "NOT VERIFIED")
        print("STAGE22 " + (verdict if valid else
              f"NOT VERIFIED ordered={ordered} cpu={cpu} timer={timer} "
              f"memory={memory} vectors={vectors} armed={armed} "
              f"diagnostic={kind} HVC={hvc} restore={restored} done={finished}"))
        if not valid:
            raise SystemExit(1)
    if args.require_stage21d:
        selected = [r for r in records if r["stage"] == 26]
        required = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911,
                    0x1930, 0x1940, 0x1941, 0x1950, 0x1951,
                    0x1952, 0x21e6, 0x21e0, 0x20a0, 0x21ea,
                    0x20a1, 0x21e1, 0x21e2, 0x21e3, 0x21e4,
                    0x21e5, 0x20b3, 0x20a3, 0x21e8, 0x20ff, 0x19ff)
        first = {}
        for index, rec in enumerate(selected):
            first.setdefault(rec["event"], index)
        ordered = all(e in first for e in required) and all(
            first[a] < first[b] for a, b in zip(required, required[1:]))

        def match(event, predicate):
            return any(r["event"] == event and predicate(r) for r in selected)

        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        admission = (match(0x1901, lambda r: r["a"] == 1) and
                     match(0x1910, lambda r: r["a"] == 1) and
                     match(0x1911, lambda r: r["a"] == 0))
        vectors = match(0x21e6, lambda r: r["el"] == 8 and
                        (r["a"], r["b"], r["c"]) ==
                        (0x81429000, 0x81429200, 0xfffffff007429000))
        armed = match(0x21e0, lambda r: r["el"] == 8 and
                      (r["a"], r["b"], r["c"]) ==
                      (0x8142d488, 0x81ac061c, 0x14000719))
        preflight = match(0x21ea, lambda r: r["el"] == 8 and
                          r["a"] == 0x81ac061c and
                          r["b"] == 0xfffffff007ac061c)
        el1 = match(0x20a1, lambda r: r["el"] == 4 and
                    (r["a"], r["b"], r["c"]) ==
                    (4, 0x8142d488, 0x824bc000))
        mmu = match(0x21e2, lambda r: r["el"] == 8 and
                    r["a"] == 0xfffffff007429000 and
                    r["b"] == 0x22a5192519 and (r["c"] & 1) == 1)
        translation = match(0x21e3, lambda r: r["el"] == 8 and
                            (r["a"], r["b"], r["c"]) ==
                            (0x8117a000, 0x8117b000, 0x0c08044f00bb44ff))
        origin = match(0x21e4, lambda r: r["el"] == 8 and
                       r["a"] in (0xfffffff007429004, 0xfffffff007429204) and
                       (r["b"] & 0xf) == 5 and (r["c"] & 0xf) in (4, 5))
        hvc = match(0x20b3, lambda r: r["el"] == 8 and
                    (r["a"] >> 26) == 0x16 and
                    (r["a"] & 0xffff) == 0x21 and
                    r["b"] in (0xfffffff007429004, 0xfffffff007429204) and
                    (r["c"] & 0xf) == 5)
        brk = match(0x21e1, lambda r: r["el"] == 8 and
                    (r["a"] >> 26) == 0x3c and
                    (r["a"] & 0xffff) == 0xe23 and
                    r["b"] == 0xfffffff007ac061c)
        fault = match(0x21e1, lambda r: r["el"] == 8 and
                      (r["a"] >> 26) != 0x3c)
        kind = (match(0x21e5, lambda r: r["a"] == 1 and
                      r["b"] == 0xfffffff007ac061c and r["c"] == 0x3c)
                if brk else
                match(0x21e5, lambda r: r["a"] == 2 and
                      r["c"] != 0x3c and
                      any(t["event"] == 0x21e1 and t["b"] == r["b"] and
                          t["a"] >> 26 == r["c"] for t in selected)))
        returned = match(0x20a3, lambda r: r["el"] == 8 and r["a"] == 8)
        restored = match(0x21e8, lambda r: r["el"] == 8 and
                         (r["a"], r["b"], r["c"]) == (1, 1, 1))
        done = all(match(e, lambda r: r["a"] == 0)
                   for e in (0x20ff, 0x19ff))
        valid = (ordered and copies and admission and vectors and armed and
                 preflight and el1 and mmu and translation and origin and
                 hvc and (brk or fault) and kind and returned and restored and
                 done and len(records) == len(selected) and
                 not (corrupt or noise or gaps or duplicates or regressions)
                 and not any(r["event"] == 0x19ee for r in selected))
        verdict = ("HIGH-VA C CHECKPOINT PASS" if brk else
                   "EARLY XNU EXCEPTION CAPTURED" if fault else "NOT VERIFIED")
        print("STAGE21-D " + (verdict if valid else
              f"NOT VERIFIED ordered={ordered} copies={copies} "
              f"vectors={vectors} trap={brk} fault={fault} "
              f"mmu={mmu} hvc={hvc} restored={restored} done={done}"))
        if not valid:
            raise SystemExit(1)
    if args.require_stage21c2:
        selected = [r for r in records if r["stage"] == 25]
        required = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911,
                    0x1930, 0x1940, 0x1941, 0x1950, 0x1951,
                    0x1952, 0x21d6, 0x21d0, 0x20a0, 0x21da,
                    0x20a1, 0x21d1, 0x21d2, 0x21d3, 0x21d4,
                    0x21d8, 0x21d5, 0x20b3, 0x20a3, 0x21d7,
                    0x20ff, 0x19ff)
        first = {}
        for index, rec in enumerate(selected):
            first.setdefault(rec["event"], index)
        ordered = all(e in first for e in required) and all(
            first[a] < first[b] for a, b in zip(required, required[1:]))
        def seen(event, predicate):
            return any(r["event"] == event and predicate(r) for r in selected)
        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        admission = (seen(0x1901, lambda r: r["a"] == 1) and
                     seen(0x1910, lambda r: r["a"] == 1) and
                     seen(0x1911, lambda r: r["a"] == 0))
        vector = seen(0x21d6, lambda r: r["el"] == 8 and
                      (r["a"], r["b"], r["c"]) ==
                      (0x81429000, 0xfffffff007429000, 0xd4000422))
        armed = seen(0x21d0, lambda r: r["el"] == 8 and
                     (r["a"], r["b"], r["c"]) ==
                     (0x8142d488, 0x8142f490, 0x14000719))
        preflight = seen(0x21da, lambda r: r["el"] == 8 and
                         r["a"] == 0x8142f490 and
                         r["b"] == 0xfffffff007429000)
        el1 = seen(0x20a1, lambda r: r["el"] == 4 and
                   (r["a"], r["b"], r["c"]) ==
                   (4, 0x8142d488, 0x824bc000))
        trapped = seen(0x21d1, lambda r: r["el"] == 8 and
                       (r["a"] >> 26) == 0x3c and
                       (r["a"] & 0xffff) == 0xe22 and
                       r["b"] == 0x8142f490)
        mmu = seen(0x21d2, lambda r: r["el"] == 8 and
                   (r["a"], r["b"], r["c"]) ==
                   (0xfffffff007429000, 0x22a5192519, 0x34d4593d))
        regs = seen(0x21d3, lambda r: r["el"] == 8 and
                    (r["a"], r["b"], r["c"]) ==
                    (0x8117a000, 0x8117b000, 0x0c08044f00bb44ff))
        roots = seen(0x21d4, lambda r:
                     (r["a"], r["b"], r["c"]) ==
                     (0x8117c003, 0x8117d003, 0x81000601))
        blocks = seen(0x21d8, lambda r:
                      (r["a"], r["b"], r["c"]) ==
                      (0x81000601, 0x8117e003, 0x9dc00601))
        origin = seen(0x21d5, lambda r:
                      r["a"] == 0xfffffff007429004 and
                      (r["b"] & 0xf) == 5 and
                      (r["c"] & 0xf) == 4)
        hvc = seen(0x20b3, lambda r: r["el"] == 8 and
                   (r["a"] >> 26) == 0x16 and
                   (r["a"] & 0xffff) == 0x21 and
                   r["b"] == 0xfffffff007429004 and
                   (r["c"] & 0xf) == 5)
        returned = seen(0x20a3, lambda r: r["el"] == 8 and r["a"] == 8)
        restored = seen(0x21d7, lambda r:
                        (r["a"], r["b"], r["c"]) == (1, 1, 1))
        finished = all(seen(e, lambda r: r["a"] == 0)
                       for e in (0x20ff, 0x19ff))
        passed = (ordered and copies and admission and vector and armed and
                  preflight and el1 and trapped and mmu and regs and roots and
                  blocks and origin and hvc and returned and restored and
                  finished and len(selected) == len(records) and
                  not (corrupt or noise or gaps or duplicates or regressions) and
                  not any(r["event"] == 0x19ee for r in selected))
        print("STAGE21-C2 " +
              ("POST-MMU EL1t VIRTUAL-VECTOR GATE PASS" if passed else
               f"NOT VERIFIED ordered={ordered} copies={copies} "
               f"admission={admission} vector={vector} armed={armed} "
               f"preflight={preflight} trap={trapped} mmu={mmu} "
               f"regs={regs} tables={roots and blocks} HVC={origin and hvc} "
               f"return={returned} restored={restored} done={finished}"))
        if not passed:
            raise SystemExit(1)
    if args.require_stage21c1:
        selected = [r for r in records if r["stage"] == 24]
        required = (0x1900, 0x1901, 0x1910, 0x1912, 0x1911,
                    0x1930, 0x1940, 0x1941, 0x1950, 0x1951,
                    0x1952, 0x21c6, 0x21c0, 0x20a0, 0x21ca, 0x20a1,
                    0x21c1, 0x21c2, 0x21c3, 0x21c4, 0x21c7,
                    0x21c8, 0x21c9, 0x20b3, 0x20a3, 0x21c5,
                    0x20ff, 0x19ff)
        first = {}
        for index, rec in enumerate(selected):
            first.setdefault(rec["event"], index)
        ordered = all(e in first for e in required) and all(
            first[a] < first[b] for a, b in zip(required, required[1:]))
        def observed(event, predicate):
            return any(r["event"] == event and predicate(r) for r in selected)
        copies = ([r["a"] for r in selected if r["event"] == 0x1940]
                  == list(range(10)) and
                  [r["a"] for r in selected if r["event"] == 0x1941]
                  == list(range(10)))
        admission = (observed(0x1901, lambda r: r["a"] == 1) and
                     observed(0x1910, lambda r: r["a"] == 1) and
                     observed(0x1911, lambda r: r["a"] == 0))
        vector = observed(0x21c6, lambda r: r["el"] == 8 and
                          (r["a"], r["b"], r["c"]) ==
                          (0x8142e000, 0x8142e000, 0xd4000422))
        armed = observed(0x21c0, lambda r: r["el"] == 8 and
                         (r["a"], r["b"], r["c"]) ==
                         (0x8142d488, 0x8142f474, 0x14000719))
        preflight = observed(0x21ca, lambda r: r["el"] == 8 and
                            r["a"] == 0x8142f474 and
                            r["b"] == 0x8142e000)
        el1 = observed(0x20a1, lambda r: r["el"] == 4 and
                       (r["a"], r["b"], r["c"]) ==
                       (4, 0x8142d488, 0x824bc000))
        trapped = observed(0x21c1, lambda r: r["el"] == 8 and
                           (r["a"] >> 26) == 0x3c and
                           (r["a"] & 0xffff) == 0xe21 and
                           r["b"] == 0x8142f474)
        mmu = observed(0x21c2, lambda r: r["el"] == 8 and
                       (r["a"], r["b"], r["c"]) ==
                       (0x8142e000, 0x22a5192519, 0x30d00800))
        regs = observed(0x21c3, lambda r: r["el"] == 8 and
                        (r["a"], r["b"], r["c"]) ==
                        (0x8117a000, 0x8117b000, 0x0c08044f00bb44ff))
        roots = observed(0x21c4, lambda r:
                         (r["a"], r["b"], r["c"]) ==
                         (0x8117c003, 0x8117d003, 0x8117e003))
        blocks = observed(0x21c7, lambda r:
                          (r["a"], r["b"], r["c"]) ==
                          (0x81000601, 0x81000601, 0x6000005e600605))
        tail = observed(0x21c8, lambda r:
                        (r["a"], r["b"], r["c"]) ==
                        (0x6000005e800605, 0, 0x9dc00601))
        hvc_origin = observed(0x21c9, lambda r:
                              r["a"] == 0x8142e004 and
                              (r["b"] & 0xf) == 5 and
                              (r["c"] & 0xf) == 4)
        hvc = observed(0x20b3, lambda r: r["el"] == 8 and
                       (r["a"] >> 26) == 0x16 and
                       (r["a"] & 0xffff) == 0x21 and
                       (r["c"] & 0xf) == 5)
        returned = observed(0x20a3, lambda r: r["el"] == 8 and
                            r["a"] == 8)
        restored = observed(0x21c5, lambda r:
                            (r["a"], r["b"], r["c"]) == (1, 1, 1))
        finished = all(observed(e, lambda r: r["a"] == 0)
                       for e in (0x20ff, 0x19ff))
        passed = (ordered and copies and admission and vector and armed and
                  preflight and
                  el1 and trapped and mmu and regs and roots and blocks and
                  tail and hvc_origin and hvc and returned and restored and
                  finished and not (corrupt or noise or gaps or duplicates or
                                    regressions) and len(selected) == len(records)
                  and not any(r["event"] == 0x19ee for r in selected))
        print("STAGE21-C1 " +
              ("PRE-MMU EL1t PAGE-TABLE GATE PASS" if passed else
               f"NOT VERIFIED ordered={ordered} copies={copies} "
               f"admission={admission} vector={vector} armed={armed} preflight={preflight} "
               f"EL1={el1} trap={trapped} mmu={mmu} regs={regs} "
               f"roots={roots} blocks={blocks} tail={tail} "
               f"HVC={hvc and hvc_origin} return={returned} "
               f"restore={restored} finish={finished}"))
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
