#!/usr/bin/env python3
"""Produce a cactus-only verified GIC MMIO recovery patch atop Stage63."""
import argparse
import difflib
import subprocess
import tempfile
from pathlib import Path

from stage61_generate_patch import SOURCE, build as stage61_patch
from stage63_generate_patch import build as stage63_patch


def build():
    source = (SOURCE / "pexpert/arm/pe_fiq.c").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as dirname:
        root = Path(dirname)
        file = root / "pexpert/arm/pe_fiq.c"
        file.parent.mkdir(parents=True)
        file.write_text(source, encoding="utf-8")
        for diff in (stage61_patch(), stage63_patch()):
            result = subprocess.run(
                ["git", "apply", "--include=pexpert/arm/pe_fiq.c", "-"],
                input=diff, text=True, cwd=root, capture_output=True)
            if result.returncode:
                raise RuntimeError(result.stderr)
        old = file.read_text(encoding="utf-8")
    new = old

    def once(original, replacement):
        nonlocal new
        if new.count(original) != 1:
            raise ValueError(f"stage64 anchor mismatch: {original[:72]!r}")
        new = new.replace(original, replacement, 1)

    once('#include <pexpert/arm64/board_config.h>', '''#include <pexpert/arm64/board_config.h>
#if defined(CACTUS)
#include <mach/vm_prot.h>
/* Reserve VA with ml_io_map, then repair its already allocated PTEs using
 * XNU's boot-time device mapping path if standard MMIO reads fail. */
extern vm_map_address_t pmap_map_bd(vm_map_address_t, vm_offset_t,
    vm_offset_t, vm_prot_t);
#endif''')

    once('''		// Find GICD base address
		gicd_base = ml_io_map(soc_base_phys + gicd_base_prop, gicd_size_prop);''', '''		// Find GICD base address
        vm_offset_t gicd_phys = soc_base_phys + gicd_base_prop;
        vm_offset_t gicr_phys = soc_base_phys + gicr_base_prop;
#if defined(CACTUS)
        /* Confirmed independently at EL2 by the Stage62/63 physical census.
         * Never use ADT arithmetic to map a different cactus GIC region. */
        if (gicd_size_prop != 0x40000ULL || gicr_size_prop != 0x200000ULL) {
            panic("ST64 cactus GIC region sizes changed: d=%llx r=%llx",
                (unsigned long long)gicd_size_prop,
                (unsigned long long)gicr_size_prop);
        }
        if (gicd_phys != 0x0c000000ULL || gicr_phys != 0x0c100000ULL) {
            kprintf("ST64 corrected ADT GIC phys: d=%llx r=%llx sizes=%llx/%llx\\n",
                (unsigned long long)gicd_phys, (unsigned long long)gicr_phys,
                (unsigned long long)gicd_size_prop, (unsigned long long)gicr_size_prop);
            gicd_phys = 0x0c000000ULL;
            gicr_phys = 0x0c100000ULL;
        }
#endif
        gicd_base = ml_io_map(gicd_phys, gicd_size_prop);''')

    once('''		gicr_base = ml_io_map(soc_base_phys + gicr_base_prop, gicr_size_prop);''',
         '''		gicr_base = ml_io_map(gicr_phys, gicr_size_prop);''')

    once('''		gicr_size = gicr_size_prop;''', '''#if defined(CACTUS)
        /* A genuine GICv3/v4 has PIDR2 architecture 3 or 4 and a
         * redistributor frame at the hardware-confirmed CPU0 PA.
         * Use XNU's backdoor PTE writer only when the VM-created IO
         * mapping reads the wrong register identity. It invalidates TLBs
         * and uses Device/noncacheable attributes; no register writes. */
        uint32_t initial_d = _gic_read32(gicd_base + 0xffe8);
        uint32_t initial_r = _gic_read32(gicr_base + CACTUS_GICR_PIDR2);
        uint64_t initial_t = _gic_read64(gicr_base + GICR_TYPER);
        kprintf("ST64 initial GICD_ID=%x GICR_ID=%x typer=%llx\\n",
            initial_d, initial_r, (unsigned long long)initial_t);
        if (((initial_d >> 4) & 15U) != 3U &&
            ((initial_d >> 4) & 15U) != 4U) {
            pmap_map_bd(gicd_base, gicd_phys, gicd_phys + gicd_size_prop,
                VM_PROT_READ | VM_PROT_WRITE);
        }
        if (((initial_r >> 4) & 15U) != 3U &&
            ((initial_r >> 4) & 15U) != 4U) {
            pmap_map_bd(gicr_base, gicr_phys, gicr_phys + gicr_size_prop,
                VM_PROT_READ | VM_PROT_WRITE);
        }
        __builtin_arm_dsb(DSB_SY);
        __builtin_arm_isb(ISB_SY);
        uint32_t after_d = _gic_read32(gicd_base + 0xffe8);
        uint32_t after_r = _gic_read32(gicr_base + CACTUS_GICR_PIDR2);
        uint64_t after_t = _gic_read64(gicr_base + GICR_TYPER);
        kprintf("ST64 mapped GIC IDs: d=%x r=%x typer=%llx\\n",
            after_d, after_r, (unsigned long long)after_t);
        if (((after_r >> 4) & 15U) != 3U &&
            ((after_r >> 4) & 15U) != 4U) {
            panic("ST64 cactus GICR unreadable after physical PTE remap: "
                "VA=%llx PA=%llx ID=%x TYPER=%llx",
                (unsigned long long)gicr_base,
                (unsigned long long)gicr_phys,
                after_r, (unsigned long long)after_t);
        }
#endif
		gicr_size = gicr_size_prop;''')

    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
        fromfile="a/pexpert/arm/pe_fiq.c", tofile="b/pexpert/arm/pe_fiq.c"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(build(), encoding="utf-8", newline="\n")
    print(args.output)
