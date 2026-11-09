#!/usr/bin/env python3
"""Prepare a newly built Cactus XNU Mach-O for the existing shim payload ABI.

The baseline payload supplies only the known-good Apple device tree, command
line and original RAM window. Never overwrite the baseline or install an
unverified image. This tool intentionally does not patch old shim opcodes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adt
import mkpayload

MAGIC = b"SWEETXNU"
MACHO_ARM64 = 0x0100000C
BASE_RAM = (0x70000000, 0x50000000)
TEST_RAM = (0x80000000, 0x1E000000)
STAGE51_LK_LAYER1 = (0x7F4DB000, 720 * 1440 * 4)
OLD_CACTUS_FB = (0x5E605000, 0x17BB000)
STAGE51_KERNEL_MARKER = b"CACTUS-XNU-STAGE51"
# macOS Clang can inline the short early-console print string, leaving no
# contiguous marker in the final Mach-O. This pinned hash belongs to the
# Stage51-only GitHub Actions CACTUS build 40099595534, whose archived
# patched source and compile logs were checked independently.
STAGE51_VERIFIED_KERNEL_SHA256 = "40f672d3500699b6ee8655e9e33e0ab29e7b410104e01618598bb9ea17d5921a"
# Filled only after the separate Stage52 CACTUS Actions kernel has compiled,
# and its build/source provenance has been verified.
STAGE52_VERIFIED_KERNEL_SHA256 = "945e61817c333218a63c80ca0bd5b237bb95ee4c6724d429ae470c8e9e8a9d36"
# Set only after Actions builds the distinct Stage53 CACTUS source patch.
STAGE53_VERIFIED_KERNEL_SHA256 = "361846aab01f80408e087e37527d774cc63766797d028bc7d701ec298a50a09e"
STAGE54_VERIFIED_KERNEL_SHA256 = "ed5123cee5377846b6485572f0594cedb1d08f8ec4ba65c68616e17fabbda81d"  # Actions run 40118509429.
STAGE55_VERIFIED_KERNEL_SHA256 = "ea16faa6d49eb135b3e7bb08477c396d994d7761e4c687cb6bffe97655e591e1"  # Actions 40123102056.
STAGE56_VERIFIED_KERNEL_SHA256 = "3004d4478977b6b29f4205fbd761774eb08f38469aabf72987658bb069a262cb"  # Successful Actions 40128807392.
STAGE57_VERIFIED_KERNEL_SHA256 = "7a0b778d113b3a66da2bc4d64c98f4ba2fef81c7ac6403f01a481ced3b396cd5"  # Successful Actions 40167462565.
STAGE58_VERIFIED_KERNEL_SHA256 = "9d6977d4f44b921677d1fac69dbb943ec785e0880d408c43a2b8d7841491b461"  # Successful Actions 40172527110.
STAGE60_VERIFIED_KERNEL_SHA256 = "2f3b02c004763c7a4bed2c9ecd58d0c789e9d5399566a862006252858c186507"  # CACTUS Actions 40177248576.
STAGE61_VERIFIED_KERNEL_SHA256 = "15fdbdab0aa0cb1f9b7cccc9b78d23b3a1f14a016b709085c621d19d9d074775"  # CACTUS Actions 40225061014.
STAGE63_VERIFIED_KERNEL_SHA256 = "c9b059c9dad73f49999c073a701fdbc2328858bbd6ccf30b18b7634222cfb51d"  # CACTUS Actions 41507227468.
STAGE65_VERIFIED_KERNEL_SHA256 = "8b9d47e456c92f59f04e546f7a047b6fb191f211fd079f274707b2bb72dfb1f5"  # CACTUS Actions 41586007450.
STAGE66_VERIFIED_KERNEL_SHA256 = "9f76552002e5ba8f71e6ab253897b14fb3f68ad08ef288d1bbdd9ab663bcc61c"  # Verified GH Actions 41588508815.
STAGE67_VERIFIED_KERNEL_SHA256 = "5fde9842617a904d5b5f75e2ca72be26d9f1c58840ff96afae54af4adc5721f7"  # Verified corrected Actions 41617481649.
STAGE68_VERIFIED_KERNEL_SHA256 = "df201510edfda5e2392ac3e8abd400e01601417ac9610b62fe19110de152a072"  # Verified Actions 41623942988.
STAGE69_VERIFIED_KERNEL_SHA256 = "c2a15e3bcca44e1ada0442c24c98fe1bc47e90ad5cfcf3670e20a93cb12e9411"  # Verified Actions 41651789127.
STAGE70_VERIFIED_KERNEL_SHA256 = "c9645c067882397d7e82e5e4bce58a3ec95035036f515162ec1580508150efaa"  # Actions 41655535161.
STAGE71_VERIFIED_KERNEL_SHA256 = "ead2ac800bac9452e7bf8e46c79bb9c2a4653ecb55c8bf344d786b353b6fb782"  # Verified Actions 41660258693.
STAGE72_VERIFIED_KERNEL_SHA256 = "3b1ae5e7f1ba8c7690d1072e68ae8d8dae9a46d7738c29e77c730d8c4b7016e3"  # Verified Actions 41666675292.
STAGE73_VERIFIED_KERNEL_SHA256 = "d5063f7f09bb5a518c02510ee5e42b28d84dce6fe7c420fc320d36076dcbba01"  # Verified Stage73 Actions.
STAGE74_VERIFIED_KERNEL_SHA256 = "d8628b44a3a2d0892606c5ebbb254883b2ff024f335cc297442095f99c467e69"
STAGE75_VERIFIED_KERNEL_SHA256 = "fd4d640bc716f1a71766d45666c73bf37394ae9f2aeb2b3adc76fee51e587803" # pin verified CI
STAGE76_VERIFIED_KERNEL_SHA256 = "7316640649e655d689c344ab5dd53623fd4971dcdcfdbb55ad48d1b27195841c" # pin after successful CI  # Fill only after successful CI artifact verification.
STAGE77_VERIFIED_KERNEL_SHA256 = "60d31b08a485278c2ea75c15b099d25af00bd6ffd78c25dc118ee9368c44bab4" # Actions 41790100285
STAGE65_VERIFIED_INIT_SHA256 = "f0b8d9f4e5d841691efe23b1521e756b743665484be82b9e7082c71626e7fe5d"
STAGE59_VERIFIED_KERNEL_SHA256 = "ed3074cc9e889f8829c29fa87f41cbe26913ad05562f94d77efefcf705595619"  # CACTUS Actions 40174697930.


def stage51_live_fb_adt(blob: bytes) -> bytes:
    """Retarget the existing Cactus console node without changing the ADT."""
    root, end = adt.parse(blob)
    if end != len(blob):
        raise ValueError("baseline Apple device tree has trailing data")
    nodes = [n for n in root.children if n.name == "sweet-fbcon"]
    if len(nodes) != 1:
        raise ValueError("expected one sweet-fbcon ADT node")
    fb = nodes[0]
    if any(
        struct.unpack("<I", fb.prop(name))[0] != expected
        for name, expected in (("width", 720), ("height", 1440), ("stride", 2880))
    ):
        raise ValueError("baseline fbcon geometry differs from verified LK layer1")
    old = fb.prop("reg")
    if old is None or len(old) != 16 or struct.unpack("<QQ", old) != OLD_CACTUS_FB:
        raise ValueError("baseline fbcon address changed unexpectedly")
    for index, (name, flags, value) in enumerate(fb.props):
        if name == "reg":
            if flags:
                raise ValueError("fbcon reg must not be a placeholder")
            fb.props[index] = (name, flags, struct.pack("<QQ", *STAGE51_LK_LAYER1))
            break
    updated = adt.serialize(root)
    if len(updated) != len(blob):
        raise ValueError("fbcon rewrite unexpectedly changed ADT size")
    return updated


def stage64_cactus_gic_adt(blob: bytes) -> bytes:
    """Replace the QEMU GIC addresses accidentally inherited by Cactus.

    Stage62/63 EL2 MMIO independently verified GICD 0x0c000000 and GICR
    0x0c100000.  /arm-io ranges has a base 0x01000000, so the device-tree
    reg pairs must be relative offsets 0x0b000000 and 0x0b100000.
    Preserve the original ADT byte length and every other property.
    """
    root, end = adt.parse(blob)
    if end != len(blob):
        raise ValueError("Stage64 ADT contains trailing bytes")
    io_nodes = [node for node in root.children if node.name == "arm-io"]
    if len(io_nodes) != 1:
        raise ValueError("Stage64 requires exactly one /arm-io")
    io = io_nodes[0]
    if io.prop("ranges") != struct.pack("<3Q", 0, 0x01000000, 0xff000000):
        raise ValueError("Stage64 unexpected SoC base/ranges")
    gic_nodes = [node for node in io.children if node.name == "gic"]
    if len(gic_nodes) != 1:
        raise ValueError("Stage64 requires exactly one /arm-io/gic")
    gic = gic_nodes[0]
    # This exact erroneous baseline was discovered by decoding Stage63's
    # shipped payload, not guessed from the device-tree generator's source.
    old_reg = struct.pack("<4Q", 0x07000000, 0x10000,
                          0x070a0000, 0x100000)
    actual_reg = struct.pack("<4Q", 0x0b000000, 0x40000,
                             0x0b100000, 0x200000)
    if gic.prop("reg") != old_reg:
        raise ValueError("Stage64 GIC baseline is no longer the audited QEMU mapping")
    for i, (name, flags, value) in enumerate(gic.props):
        if name == "reg":
            if flags:
                raise ValueError("Stage64 GIC reg cannot be a placeholder")
            gic.props[i] = (name, flags, actual_reg)
            break
    result = adt.serialize(root)
    if len(result) != len(blob):
        raise ValueError("Stage64 patch unexpectedly changed ADT length")
    return result


def baseline_metadata(data: bytes):
    if len(data) < 0x2A8 or data[:8] != MAGIC:
        raise ValueError("baseline does not contain a SWEETXNU payload")
    version, count = struct.unpack_from("<II", data, 8)
    if version != 1 or not 1 <= count <= 64:
        raise ValueError("unsupported baseline payload version or segment count")
    virt, entry, adt_off, adt_size, kend, phys, size = struct.unpack_from(
        "<7Q", data, 0x10
    )
    if (phys, size) != BASE_RAM:
        raise ValueError("expected the original, pre-Stage18 Cactus RAM layout")
    if (adt_off & 7) or adt_size < 44 or adt_off + adt_size > len(data):
        raise ValueError("invalid baseline device-tree bounds")
    cmdline = data[0x48:0x2A8].split(b"\0", 1)[0].decode("ascii")
    adt = data[adt_off:adt_off + adt_size]
    if mkpayload.adt_dram(adt) != BASE_RAM:
        raise ValueError("baseline device tree disagrees with payload RAM bounds")
    return {
        "virt": virt, "entry": entry, "kernel_end": kend,
        "cmdline": cmdline, "adt": adt, "nsegs": count,
    }


def prepare(kernel: Path, baseline: Path, output: Path, stage51_live_fb=False,
            stage52_live_fb=False, stage53_live_fb=False, stage54_live_fb=False,
            stage55_live_fb=False, stage56_live_fb=False,
            stage57_live_fb=False, stage58_live_fb=False, stage59_live_fb=False, stage60_live_fb=False,
            stage61_live_fb=False, stage64_cactus_gic=False,
            stage65_cactus_pid1=False, stage66_topbar=False,
            stage67_vfs_probe=False, stage68_root_pid1=False, stage69_root_pid1=False,
            stage70_minimal_pid1=False, stage71_direct_pid1=False,
            stage72_mockfs_pid1=False, stage73_pid1_vm=False, stage74_physmap_pid1=False, stage75_exec_read=False, stage76_pid1_shadow=False, stage77_pid1_wired=False,
            ramdisk: Path | None = None, extra_boot_args: str = "",
            root_device: str = "md0"):
    if stage77_pid1_wired and not stage76_pid1_shadow:
        raise ValueError("Stage77 requires Stage76")
    if stage76_pid1_shadow and not stage75_exec_read:
        raise ValueError("Stage76 requires Stage75 PID1 exec read")
    if stage75_exec_read and not stage74_physmap_pid1:
        raise ValueError("Stage75 requires Stage74 PID1 physical copy")
    if stage74_physmap_pid1 and not stage73_pid1_vm:
        raise ValueError("Stage74 requires Stage73 PID1 VM baseline")
    if stage73_pid1_vm and not stage72_mockfs_pid1:
        raise ValueError("Stage73 requires Stage72 mockfs/PID1 baseline")
    if stage72_mockfs_pid1 and not stage71_direct_pid1:
        raise ValueError("Stage72 requires Stage71 direct PID1 baseline")
    if stage71_direct_pid1 and not stage70_minimal_pid1:
        raise ValueError("Stage71 requires Stage70 minimal BSD startup baseline")
    if stage70_minimal_pid1 and not stage69_root_pid1:
        raise ValueError("Stage70 requires Stage69 BSD/root/PID1 checkpoint baseline")
    if stage69_root_pid1 and not stage68_root_pid1:
        raise ValueError("Stage69 requires Stage68 root/PID1 baseline")
    if stage68_root_pid1 and not stage67_vfs_probe:
        raise ValueError("Stage68 requires Stage67 VFS/visible PID1 baseline")
    if stage67_vfs_probe and not stage66_topbar:
        raise ValueError("Stage67 requires Stage66 status-bar and PID1 pins")
    if stage66_topbar and not stage65_cactus_pid1:
        raise ValueError("Stage66 requires existing PID1 syscall proof and corrected GIC")
    if stage65_cactus_pid1 and not stage64_cactus_gic:
        raise ValueError("Stage65 requires corrected GIC Apple device tree")
    if stage65_cactus_pid1 and (
        ramdisk is None or
        hashlib.sha256(ramdisk.read_bytes()).hexdigest() != STAGE65_VERIFIED_INIT_SHA256
    ):
        raise ValueError("Stage65 requires the audited diagnostic PID1")
    if stage64_cactus_gic and not stage61_live_fb:
        raise ValueError("Stage64 requires audited Stage63 live-fb payload mode")
    if sum((stage51_live_fb, stage52_live_fb, stage53_live_fb,
            stage54_live_fb, stage55_live_fb, stage56_live_fb,
            stage57_live_fb, stage58_live_fb, stage59_live_fb, stage60_live_fb,
            stage61_live_fb)) > 1:
        raise ValueError("Stage51ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ59 selections are exclusive")
    if ramdisk is not None and not (stage55_live_fb or stage56_live_fb or stage57_live_fb or stage58_live_fb or stage59_live_fb or stage60_live_fb or stage61_live_fb):
        raise ValueError("diagnostic RAMDisk requires audited Stage55ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ59")
    if output.resolve() in (kernel.resolve(), baseline.resolve()):
        raise ValueError("refusing to overwrite either input")
    kdata = kernel.read_bytes()
    if len(kdata) < 4096:
        raise ValueError("new kernel file is too small to be a Mach-O")
    kernel_sha256 = hashlib.sha256(kdata).hexdigest()
    if stage51_live_fb and (STAGE51_KERNEL_MARKER not in kdata and
                             kernel_sha256 != STAGE51_VERIFIED_KERNEL_SHA256):
        raise ValueError(
            "Stage51 XNU build provenance missing: kernel neither contains "
            "the console marker nor matches the verified Stage51 build hash"
        )
    if stage52_live_fb and kernel_sha256 != STAGE52_VERIFIED_KERNEL_SHA256:
        raise ValueError(
            "Stage52 XNU Mach-O hash does not match the verified Stage52 build"
        )
    if stage53_live_fb and (
        not STAGE53_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE53_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError(
            "Stage53 XNU Mach-O hash does not match the verified Stage53 build"
        )
    if stage54_live_fb and (
        not STAGE54_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE54_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage54 XNU Mach-O does not match the verified Stage54 build")
    if stage55_live_fb and (
        not STAGE55_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE55_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage55 kernel provenance has not been verified")
    if stage56_live_fb and (
        not STAGE56_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE56_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage56 kernel provenance has not been verified")
    if stage57_live_fb and (
        not STAGE57_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE57_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage57 kernel provenance has not been verified")
    if stage58_live_fb and (
        not STAGE58_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE58_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage58 kernel provenance has not been verified")
    if stage59_live_fb and (
        not STAGE59_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE59_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage59 kernel provenance has not been verified")
    if stage60_live_fb and (
        not STAGE60_VERIFIED_KERNEL_SHA256 or
        kernel_sha256 != STAGE60_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage60 kernel provenance has not been verified")
    if stage61_live_fb and kernel_sha256 != (
        STAGE77_VERIFIED_KERNEL_SHA256 if stage77_pid1_wired else
        STAGE76_VERIFIED_KERNEL_SHA256 if stage76_pid1_shadow else
        STAGE75_VERIFIED_KERNEL_SHA256 if stage75_exec_read else
        STAGE74_VERIFIED_KERNEL_SHA256 if stage74_physmap_pid1 else
        STAGE73_VERIFIED_KERNEL_SHA256 if stage73_pid1_vm else
        STAGE72_VERIFIED_KERNEL_SHA256 if stage72_mockfs_pid1 else
        STAGE71_VERIFIED_KERNEL_SHA256 if stage71_direct_pid1 else
        STAGE70_VERIFIED_KERNEL_SHA256 if stage70_minimal_pid1 else
        STAGE69_VERIFIED_KERNEL_SHA256 if stage69_root_pid1 else
        STAGE68_VERIFIED_KERNEL_SHA256 if stage68_root_pid1 else
        STAGE67_VERIFIED_KERNEL_SHA256 if stage67_vfs_probe else
        STAGE66_VERIFIED_KERNEL_SHA256 if stage66_topbar else
        STAGE65_VERIFIED_KERNEL_SHA256 if stage65_cactus_pid1 else
        STAGE63_VERIFIED_KERNEL_SHA256 if stage64_cactus_gic else
        STAGE61_VERIFIED_KERNEL_SHA256
    ):
        raise ValueError("Stage61/64 kernel provenance has not been verified")
    km = mkpayload.parse_macho(kdata)
    if km["cputype"] != MACHO_ARM64 or not km["entry"]:
        raise ValueError("expected a real arm64 XNU Mach-O with a UNIXTHREAD PC")
    if not km["segs"] or km["segs"][0]["name"] != "__TEXT":
        raise ValueError("expected an XNU Mach-O starting in __TEXT")
    old = baseline_metadata(baseline.read_bytes())
    # Windows/Codex sandbox can deny writes under the process-default
    # %TEMP%; use the caller's already-writable build-output directory.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        adt_path = Path(temporary) / "original-cactus.adt"
        adt_blob = (
            stage51_live_fb_adt(old["adt"]) if (stage51_live_fb or stage52_live_fb or stage53_live_fb or stage54_live_fb or stage55_live_fb or stage56_live_fb or stage57_live_fb or stage58_live_fb or stage59_live_fb or stage60_live_fb or stage61_live_fb)
            else old["adt"]
        )
        if stage64_cactus_gic:
            adt_blob = stage64_cactus_gic_adt(adt_blob)
        adt_path.write_bytes(adt_blob)
        cmdline = old["cmdline"]
        if root_device not in ("md0", "emmcroot0"):
            raise ValueError(f"unsupported cactus root selection: {root_device}")
        if root_device != "md0" and ramdisk is None:
            raise ValueError("external root requires the audited RAMDisk payload layout")
        if ramdisk is not None:
            if not ramdisk.is_file() or ramdisk.stat().st_size == 0:
                raise ValueError("diagnostic RAMDisk is absent or empty")
            if any(arg.startswith("rd=") for arg in cmdline.split()):
                raise ValueError("baseline already has a root-device argument")
            cmdline = cmdline.strip() + " rd=" + root_device
        if extra_boot_args:
            if not extra_boot_args.isascii() or "\x00" in extra_boot_args or len(extra_boot_args) > 256:
                raise ValueError("invalid additional boot arguments")
            cmdline = cmdline.strip() + " " + extra_boot_args.strip()
        new, info = mkpayload.build(str(kernel), str(adt_path), cmdline,
                                    str(ramdisk) if ramdisk is not None else None)
    if info["cputype"] != hex(MACHO_ARM64):
        raise ValueError("repacked image lost arm64 architecture")
    if not info["entry"].startswith("0x"):
        raise ValueError("missing new XNU entry PC")
    if info["virt_base"] != hex(old["virt"]):
        raise ValueError("virtual RAM base changed; loader requires a new layout audit")
    version, count = struct.unpack_from("<II", new, 8)
    virt, entry, adt_off, adt_size, kend, phys, size = struct.unpack_from(
        "<7Q", new, 0x10
    )
    if (version, phys, size) != (1, *BASE_RAM) or not 1 <= count <= 64:
        raise ValueError("new kernel wrapper ABI/RAM bounds changed")
    if kend < virt or (kend - virt + adt_size + 0x8000) > TEST_RAM[1]:
        raise ValueError("kernel, device tree and boot_args do not fit test RAM")
    if mkpayload.adt_dram(new[adt_off:adt_off+adt_size]) != BASE_RAM:
        raise ValueError("generated device-tree RAM bounds changed")
    if stage51_live_fb or stage52_live_fb or stage53_live_fb or stage54_live_fb or stage55_live_fb or stage56_live_fb or stage57_live_fb or stage58_live_fb or stage59_live_fb or stage60_live_fb or stage61_live_fb:
        root, end = adt.parse(new[adt_off:adt_off+adt_size])
        nodes = [n for n in root.children if n.name == "sweet-fbcon"]
        if end != adt_size or len(nodes) != 1 or (
            struct.unpack("<QQ", nodes[0].prop("reg")) != STAGE51_LK_LAYER1
        ):
            raise ValueError("generated Stage51 payload did not retain live fbcon")
    if old["entry"] == entry:
        # Identical startup PC can occur after source-only changes, but a
        # byte-identical payload would mean the rebuilt XNU was not selected.
        if hashlib.sha256(new).digest() == hashlib.sha256(baseline.read_bytes()).digest():
            raise ValueError("new kernel produced the identical baseline payload")
    if ramdisk is not None:
        root, end = adt.parse(new[adt_off:adt_off+adt_size])
        chosen = next(n for n in root.children if n.name == "chosen")
        mmap = next(n for n in chosen.children if n.name == "memory-map")
        rd = mmap.prop("RAMDisk")
        if end != adt_size or rd is None or len(rd) != 16:
            raise ValueError("Stage55 RAMDisk memory map was not recorded")
        rd_pa, rd_size = struct.unpack("<QQ", rd)
        # Packer output is still in its pre-Stage18 0x70000000 RAM window;
        # the relocation script shifts it to 0x80000000 for the shim.
        if rd_pa < BASE_RAM[0] or rd_pa + rd_size > BASE_RAM[0] + BASE_RAM[1]:
            raise ValueError("Stage55 source RAMDisk is outside pinned RAM")
        if (rd_pa & 0x3fff) or (rd_size & 0x3fff):
            raise ValueError("Stage55 RAMDisk layout must be 16KiB aligned")
    output.write_bytes(new)
    report = {
        "kernel": str(kernel), "kernel_sha256": hashlib.sha256(kdata).hexdigest(),
        "baseline": str(baseline), "payload": str(output),
        "payload_sha256": hashlib.sha256(new).hexdigest(),
        "segment_count": count, "entry_va": hex(entry),
        "virt_base": hex(virt), "kernel_end_va": hex(kend),
        "source_ram": [hex(phys), hex(size)],
        "chained_fixups": info["fixups"],
        "stage18_relocation_required": True,
        "shim_boot_image_ready": False,
        "stage51_live_fb": stage51_live_fb,
        "stage52_live_fb": stage52_live_fb,
        "stage53_live_fb": stage53_live_fb,
        "stage54_live_fb": stage54_live_fb,
        "stage55_live_fb": stage55_live_fb,
        "stage56_live_fb": stage56_live_fb,
        "stage57_live_fb": stage57_live_fb,
        "stage58_live_fb": stage58_live_fb,
        "stage59_live_fb": stage59_live_fb,
        "stage60_live_fb": stage60_live_fb,
        "stage61_live_fb": stage61_live_fb,
        "stage64_cactus_gic": stage64_cactus_gic,
        "stage65_cactus_pid1": stage65_cactus_pid1,
        "stage66_topbar": stage66_topbar,
        "stage67_vfs_probe": stage67_vfs_probe,
        "stage68_root_pid1": stage68_root_pid1,
        "stage69_root_pid1": stage69_root_pid1,
        "stage70_minimal_pid1": stage70_minimal_pid1,
        "stage71_direct_pid1": stage71_direct_pid1,
        "stage72_mockfs_pid1": stage72_mockfs_pid1,
        "stage73_pid1_vm": stage73_pid1_vm,
        "stage74_physmap_pid1": stage74_physmap_pid1,
        "stage75_exec_read": stage75_exec_read,
        "stage76_pid1_shadow": stage76_pid1_shadow,
        "stage77_pid1_wired": stage77_pid1_wired,
        "ramdisk_source": str(ramdisk) if ramdisk is not None else None,
        "stage51_kernel_marker_present": STAGE51_KERNEL_MARKER in kdata if stage51_live_fb else None,
        "stage51_kernel_provenance": (
            "compiled_marker" if STAGE51_KERNEL_MARKER in kdata
            else "github_run_40099595534_sha256_pin"
        ) if stage51_live_fb else None,
    }
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path, help="downloaded XNU Mach-O")
    parser.add_argument("baseline", type=Path, help="old unrelocated payload.bin")
    parser.add_argument("output", type=Path, help="new separately named payload")
    parser.add_argument("--stage51-live-fb", action="store_true",
                        help="update baseline Cactus ADT fbcon to verified LK layer1")
    parser.add_argument("--stage52-live-fb", action="store_true",
                        help="use pinned Stage52 Cactus XNU and live LK layer1 ADT")
    parser.add_argument("--stage53-live-fb", action="store_true",
                        help="use exact verified Stage53 XNU with persistent framebuffer status")
    parser.add_argument("--stage54-live-fb", action="store_true",
                        help="use exact verified Stage54 Cactus XNU with IOKit/BSD progress")
    parser.add_argument("--stage55-live-fb", action="store_true",
                        help="use exact verified Stage55 BSD-gate XNU kernel")
    parser.add_argument("--stage56-live-fb", action="store_true",
                        help="use exact audited Stage56 CPU diagnostics XNU kernel")
    parser.add_argument("--stage57-live-fb", action="store_true",
                        help="use exact audited Stage57 CPU0 interrupt recovery XNU kernel")
    parser.add_argument("--stage58-live-fb", action="store_true",
                        help="use exact audited Stage58 GICv3 interrupt snapshot and rearm XNU kernel")
    parser.add_argument("--stage59-live-fb", action="store_true",
                        help="use exact audited Stage59 IRQ-independent CPU0 retry XNU kernel")
    parser.add_argument("--stage60-live-fb", action="store_true",
                        help="use verified Stage60 Group1 SGI8 XNU kernel")
    parser.add_argument("--stage61-live-fb", action="store_true",
                        help="use SHA-pinned Stage61 GICR identity guarded XNU kernel")
    parser.add_argument("--stage64-cactus-gic", action="store_true",
                        help="Stage63 native kernel with physically verified cactus GIC ADT")
    parser.add_argument("--stage65-cactus-pid1", action="store_true",
                        help="Stage65 SHA-pinned PID1 proof with corrected GIC ADT")
    parser.add_argument("--stage66-topbar", action="store_true",
                        help="Stage66 SHA-pinned visible PID1 status above Cactarwin banner")
    parser.add_argument("--stage67-vfs-probe", action="store_true",
                        help="Stage67 pins VFS/decmpfs progress probes and visible PID1 bar")
    parser.add_argument("--stage68-root-pid1", action="store_true",
                        help="Stage68 pins BSD post-VFS/root mount/initproc/exec checkpoints")
    parser.add_argument("--stage69-root-pid1", action="store_true",
                        help="Stage69 pins BSD intermediate initializers and root lookup checkpoints")
    parser.add_argument("--stage70-minimal-pid1", action="store_true",
                        help="Stage70 uses CACTUS minimal optional-networking startup for PID1")
    parser.add_argument("--stage71-direct-pid1", action="store_true",
                        help="Stage71 fixes mockfs ops and directly execs diagnostic /sbin/launchd")
    parser.add_argument("--stage72-mockfs-pid1", action="store_true",
                        help="Stage72 fixes mockfs executable vnode POSIX mode and path lookup")
    parser.add_argument("--stage73-pid1-vm", action="store_true",
                        help="Stage73 allocates and copies PID1 exec arguments in the process task VM map")
    parser.add_argument("--stage74-physmap-pid1", action="store_true",
                        help="Stage74 wires target PID1 VM pages and populates via physmap")
    parser.add_argument("--stage75-exec-read", action="store_true",
                        help="Stage75 reads first PID1 exec strings via scratch physical alias")
    parser.add_argument("--stage76-pid1-shadow", action="store_true",
                        help="Stage76 reads PID1 exec strings from the mirrored argument scratch page")
    parser.add_argument("--stage77-pid1-wired", action="store_true",
                        help="Stage77 wires PID1 execargs and bounded shadow pathname")
    parser.add_argument("--ramdisk", type=Path,
                        help="optional Stage55 source-built static PID1 root (rd=md0)")
    args = parser.parse_args()
    prepare(args.kernel, args.baseline, args.output,
            stage51_live_fb=args.stage51_live_fb,
            stage52_live_fb=args.stage52_live_fb,
            stage53_live_fb=args.stage53_live_fb,
            stage54_live_fb=args.stage54_live_fb,
            stage55_live_fb=args.stage55_live_fb,
            stage56_live_fb=args.stage56_live_fb,
            stage57_live_fb=args.stage57_live_fb,
            stage58_live_fb=args.stage58_live_fb,
            stage59_live_fb=args.stage59_live_fb,
            stage60_live_fb=args.stage60_live_fb,
            stage61_live_fb=args.stage61_live_fb,
            stage64_cactus_gic=args.stage64_cactus_gic,
            stage65_cactus_pid1=args.stage65_cactus_pid1,
            stage66_topbar=args.stage66_topbar,
            stage67_vfs_probe=args.stage67_vfs_probe,
            stage68_root_pid1=args.stage68_root_pid1,
            stage69_root_pid1=args.stage69_root_pid1,
            stage70_minimal_pid1=args.stage70_minimal_pid1,
            stage71_direct_pid1=args.stage71_direct_pid1,
            stage72_mockfs_pid1=args.stage72_mockfs_pid1,
            stage73_pid1_vm=args.stage73_pid1_vm,
            stage74_physmap_pid1=args.stage74_physmap_pid1,
            stage75_exec_read=args.stage75_exec_read,
            stage76_pid1_shadow=args.stage76_pid1_shadow,
            stage77_pid1_wired=args.stage77_pid1_wired, ramdisk=args.ramdisk)
