#!/usr/bin/env python3
"""Produce a fail-closed Cactus GICR identity and SGI enable repair candidate.

Input consists of the isolated Stage60 patched source images.  This never
changes the live XNU tree or any earlier patch.
"""
from pathlib import Path
import argparse
import difflib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shim/out/cactus/stage61-source"


def replace_once(value, old, new, desc):
    count = value.count(old)
    if count != 1:
        raise ValueError(f"{desc}: expected one match, found {count}")
    return value.replace(old, new)


def build():
    originals = {}
    changed = {}
    for rel in ("pexpert/pexpert/arm64/CACTUS.h",
                "pexpert/arm/pe_fiq.c",
                "iokit/Kernel/arm/SweetCPU.cpp"):
        originals[rel] = (SOURCE / rel).read_text(encoding="utf-8")
        changed[rel] = originals[rel]

    rel = "pexpert/pexpert/arm64/CACTUS.h"
    changed[rel] = replace_once(changed[rel],
        "#define GICR_TYPER                              0x08",
        "#define GICR_TYPER                              0x08\n"
        "#define CACTUS_GICR_PIDR2                      0xffe8 // GICR ID register",
        "pidr2-header")

    rel = "pexpert/arm/pe_fiq.c"
    s = changed[rel]
    s = replace_once(s,
        "static vm_offset_t gicr_size;",
        """static vm_offset_t gicr_size;
#if defined(CACTUS)
/* Log each redistributor identity outcome just once; find_gicr_pe_base is
 * called in CPU readiness loops and must not flood the framebuffer. */
static unsigned int cactus_gicr_diag_bits;
#endif""",
        "one-time-gicr-log")
    s = replace_once(s,
        "\t\tuint64_t gicr_typer = gicr_read64(GICR_TYPER);",
        """#if defined(CACTUS)
        /* A zero-filled or incorrectly mapped GICR frame has affinity 0.
         * Without this check CPU0 falsely accepts it and all SGI enable
         * writes disappear. Verify the architected GICv3/v4 PIDR2 first. */
        uint32_t pidr2 = gicr_read32(CACTUS_GICR_PIDR2);
        uint32_t architecture = (pidr2 >> 4) & 0xfU;
        if (architecture != 3U && architecture != 4U) {
            if (!(__atomic_fetch_or(&cactus_gicr_diag_bits, 1U, __ATOMIC_RELAXED) & 1U)) {
                kprintf("ST61 bad GICR frame offset=0x%llx pidr2=%x\\n",
                    (unsigned long long)offset, pidr2);
            }
            continue;
        }
#endif
        uint64_t gicr_typer = gicr_read64(GICR_TYPER);""",
        "reject-unmapped-gicr")
    s = replace_once(s,
        "\t\tif (phys_id == aff_value) {\n\t\t\treturn gicr_pe_base;",
        """        if (phys_id == aff_value) {
#if defined(CACTUS)
            if (!(__atomic_fetch_or(&cactus_gicr_diag_bits, 2U, __ATOMIC_RELAXED) & 2U)) {
                kprintf("ST61 GICR match offset=0x%llx typer=0x%llx pidr2=%x\\n",
                    (unsigned long long)offset, (unsigned long long)gicr_typer,
                    gicr_read32(CACTUS_GICR_PIDR2));
            }
#endif
            return gicr_pe_base;""",
        "chosen-gicr-id")
    s = replace_once(s,
        '    kprintf("ST60 GICR pre: ctlr=%x waker=%x group=%x mod=%x nsacr=%x enable=%x pending=%x\\n",',
        '    kprintf("ST61 GICR pre: ctlr=%x waker=%x group=%x mod=%x nsacr=%x enable=%x pending=%x\\n",',
        "stage61-pre")
    s = replace_once(s,
        '    kprintf("ST60 GICR post: ctlr=%x group=%x mod=%x enable=%x pending=%x\\n",',
        '    kprintf("ST61 GICR post: ctlr=%x group=%x mod=%x enable=%x pending=%x\\n",',
        "stage61-post")
    s = replace_once(s,
        '        gicr_read32(0x10200));\n    if (!(__builtin_arm_rsr64("ICC_SRE_EL1") & ICC_SRE_SRE)) {',
        '''        gicr_read32(0x10200));
    uint32_t enable_after = gicr_read32(GICR_ISENABLER0);
    uint32_t sgi = 1U << SWEET_IPI_SGI;
    uint32_t timer = 1U << sweet_vtimer_intid;
    kprintf("ST61 GICR enable result: SGI=%u PPI=%u id=%x group=%x\\n",
        !!(enable_after & sgi), !!(enable_after & timer),
        gicr_read32(CACTUS_GICR_PIDR2), gicr_read32(GICR_IGROUPR0));
    if (!(__builtin_arm_rsr64("ICC_SRE_EL1") & ICC_SRE_SRE)) {''',
        "separate-timer-and-sgi")
    changed[rel] = s

    rel = "iokit/Kernel/arm/SweetCPU.cpp"
    s = changed[rel]
    s = replace_once(s,
        '\t\t\t\tIOLog("ST60 GIC SGI8 rearm status=0x%llx\\n",',
        '\t\t\t\tIOLog("ST61 GIC SGI8 rearm status=0x%llx\\n",',
        "status-tag")
    s = replace_once(s,
        '"ST60 SGI8 enable blocked"', '"ST61 SGI8 ENABLE WRITE LOST"', "enable-tag")
    s = replace_once(s,
        '"ST60 SGI8 enabled"', '"ST61 SGI8 ENABLE OK"', "enable-ok-tag")
    s = replace_once(s,
        '\t\t\t\tfbcon_stage53_progress("ST60 SGI8 sent");',
        '''                /* Preserve the outcome in STATUS even after sending:
                 * a successful ICC_SGI1R write does not prove delivery. */
                fbcon_stage53_progress((after & 0x40) ?
                    "ST61 SGI8 SENT, ENABLE=0" :
                    "ST61 SGI8 SENT, ENABLE=1");''',
        "persistent-final-status")
    s = replace_once(s,
        '\t\t\t\tfbcon_stage53_progress((state & 1) ? "ST58 TIMEOUT IRQ MASK" :',
        '''                fbcon_stage53_progress((state & 0x40) ?
                    "ST61 TIMEOUT SGI8 DISABLED" :
                    (state & 1) ? "ST61 TIMEOUT IRQ MASK" :''',
        "timeout-reason")
    changed[rel] = s

    result = []
    for rel in originals:
        result.extend(difflib.unified_diff(originals[rel].splitlines(True),
            changed[rel].splitlines(True), fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = build()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(result, encoding="utf-8", newline="\n")
    print("STAGE61_PATCH", arguments.output, len(result))
