#!/usr/bin/env python3
"""Build Stage63 native GIC map/readback diagnostics over audited Stage61 source."""
import argparse
import difflib
from pathlib import Path

from stage61_generate_patch import ROOT, SOURCE, build as stage61_patch


def build():
    source = (SOURCE / "pexpert/arm/pe_fiq.c").read_text(encoding="utf-8")
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        file = root / "pexpert/arm/pe_fiq.c"
        file.parent.mkdir(parents=True)
        file.write_text(source, encoding="utf-8")
        result = subprocess.run(["git", "apply", "--include=pexpert/arm/pe_fiq.c", "-"], input=stage61_patch(),
                                text=True, cwd=root, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        original = file.read_text(encoding="utf-8")
    updated = original

    def replace_once(needle, new):
        nonlocal updated
        if updated.count(needle) != 1:
            raise ValueError(f"Expected exactly one match: {needle[:60]}")
        updated = updated.replace(needle, new, 1)

    needle = "\tfor (vm_offset_t offset = 0; offset < gicr_size; offset += GICR_PE_SIZE) {"
    replace_once(needle, '''#if defined(CACTUS)
    kprintf("ST63 scan mpidr=%llx gicr_va=%llx bytes=%llx\\n",
        (unsigned long long)__builtin_arm_rsr64("MPIDR_EL1"),
        (unsigned long long)gicr_base, (unsigned long long)gicr_size);
#endif
''' + needle)
    needle = "        uint32_t architecture = (pidr2 >> 4) & 0xfU;"
    replace_once(needle, needle + '''
        uint64_t stage63_typer = gicr_read64(GICR_TYPER);
        kprintf("ST63 frame off=%llx pidr2=%x typer=%llx affinity=%x\\n",
            (unsigned long long)offset, pidr2,
            (unsigned long long)stage63_typer, (unsigned)(stage63_typer >> 32));''')
    needle = "\t\t// Find GICD base address"
    replace_once(needle, '''#if defined(CACTUS)
        kprintf("ST63 ADT soc=%llx gicd_off=%llx gicr_off=%llx gicr_pa=%llx size=%llx\\n",
            (unsigned long long)soc_base_phys,
            (unsigned long long)gicd_base_prop,
            (unsigned long long)gicr_base_prop,
            (unsigned long long)(soc_base_phys + gicr_base_prop),
            (unsigned long long)gicr_size_prop);
#endif
''' + needle)
    needle = "\t\tgicr_size = gicr_size_prop;"
    replace_once(needle, '''#if defined(CACTUS)
        kprintf("ST63 GIC mapped gicd_va=%llx gicr_va=%llx\\n",
            (unsigned long long)gicd_base, (unsigned long long)gicr_base);
#endif
''' + needle)
    return "".join(difflib.unified_diff(original.splitlines(True),
        updated.splitlines(True), fromfile="a/pexpert/arm/pe_fiq.c",
        tofile="b/pexpert/arm/pe_fiq.c"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(build(), encoding="utf-8", newline="\n")
    print(args.output)
