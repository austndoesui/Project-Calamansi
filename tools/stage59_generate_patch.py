#!/usr/bin/env python3
"""Generate Stage59 CPU0 SGI/timer deadlock recovery patch from Stage58 sources.

The input tree must have Stage56/57/58 applied. This generator never modifies
the source tree and rejects ambiguous matches.
"""
import argparse
import difflib
from pathlib import Path


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise ValueError(f"{label}: expected one match, found {n}")
    return text.replace(old, new)


EDITS = {
    "iokit/Kernel/arm/SweetCPU.cpp": [
        ("\t\tuint64_t retry_at;\n\t\tnanoseconds_to_deadline(250000000ULL, &retry_at);\n",
         "\t\t/* First retry must happen immediately: IOSleep and timed waits\n"
         "\t\t * can never wake while CPU0's interrupt source is disabled. */\n"
         "\t\tuint64_t retry_at = mach_absolute_time();\n", "initial-retry-deadline"),
        ("\t\t\t\tfbcon_stage53_progress(\"ST58 GICv3 rearm SGI1\");\n"
         "\t\t\t\tcactus_gicv3_cpu0_rearm();\n"
         "\t\t\t\tcpu->signalCPU(cpu);\n"
         "\t\t\t\tfbcon_stage53_progress(\"ST58 CPU0 SGI1 retried\");\n",
         "\t\t\t\tfbcon_stage53_progress(\"ST59 GIC SGI1 rearm\");\n"
         "\t\t\t\tcactus_gicv3_cpu0_rearm();\n"
         "\t\t\t\tuint64_t after = cactus_gicv3_cpu0_snapshot();\n"
         "\t\t\t\tIOLog(\"ST59 GIC SGI after rearm status=0x%llx\\n\",\n"
         "\t\t\t\t    (unsigned long long)after);\n"
         "\t\t\t\tfbcon_stage53_progress((after & 0x40) ?\n"
         "\t\t\t\t    \"ST59 SGI1 enable not latched\" :\n"
         "\t\t\t\t    \"ST59 SGI1 enabled\");\n"
         "\t\t\t\tcpu->signalCPU(cpu);\n"
         "\t\t\t\tfbcon_stage53_progress(\"ST59 SGI1 sent\");\n", "immediate-rearm-and-readback"),
        ("\t\t\t}\n\t\t\tIOSleep(1);\n\t\t}\n\t\tIOLog(\"SWEET CPU: cpu=%u mpidr=0x%x came alive; SGI1 OK\\n\",",
         "\t\t\t}\n"
         "\t\t\tif (i == topology->boot_cpu->cpu_id && initialized && !signal_ready) {\n"
         "\t\t\t\t/* A missing GIC timer IRQ makes IOSleep a deadlock. Use the\n"
         "\t\t\t\t * counter-backed short busy wait until SGI1 arrives or\n"
         "\t\t\t\t * the existing bounded timeout reports the fault. */\n"
         "\t\t\t\tIODelay(100);\n"
         "\t\t\t} else {\n"
         "\t\t\t\tIOSleep(1);\n"
         "\t\t\t}\n"
         "\t\t}\n\t\tIOLog(\"SWEET CPU: cpu=%u mpidr=0x%x came alive; SGI1 OK\\n\",",
         "counter-backed-spin"),
    ],
    "pexpert/arm/pe_fiq.c": [
        ("\tgicr_write32(GICR_ISENABLER0, (1U << sweet_vtimer_intid) | (1U << SWEET_IPI_SGI));\n",
         "\tgicr_write32(GICR_ISENABLER0, (1U << sweet_vtimer_intid) | (1U << SWEET_IPI_SGI));\n"
         "#if defined(CACTUS)\n"
         "\t/* Cactus SGI1 was observed disabled at the first Stage58 snapshot.\n"
         "\t * Read back after the GICR write to separate a failed enable\n"
         "\t * (security/redistributor) from later priority/masking failures. */\n"
         "\t__builtin_arm_dsb(DSB_SY);\n"
         "\tkprintf(\"ST59 GICR after pe_init enable=0x%x wake=0x%x\\n\",\n"
         "\t    gicr_read32(GICR_ISENABLER0), gicr_read32(GICR_WAKER));\n"
         "#endif\n", "gicr-initial-readback"),
        ("    if (gicr_read32(GICR_WAKER) & GICR_WAKER_PROCESSORSLEEP) {\n"
         "        gicr_write32(GICR_WAKER,\n"
         "            gicr_read32(GICR_WAKER) & ~GICR_WAKER_PROCESSORSLEEP);\n"
         "    }\n    gicr_write32(GICR_IGROUPR0, 0xFFFFFFFFU);\n",
         "    if (gicr_read32(GICR_WAKER) & GICR_WAKER_PROCESSORSLEEP) {\n"
         "        gicr_write32(GICR_WAKER,\n"
         "            gicr_read32(GICR_WAKER) & ~GICR_WAKER_PROCESSORSLEEP);\n"
         "    }\n"
         "\t/* The redistributor wake is asynchronous; wait before touching\n"
         "\t * SGI-frame registers. Bound it so a broken GIC cannot hang. */\n"
         "    uint64_t wake_deadline;\n"
         "    nanoseconds_to_deadline(10000000ULL, &wake_deadline);\n"
         "    while (gicr_read32(GICR_WAKER) & GICR_WAKER_CHILDRENASLEEP) {\n"
         "        if (mach_absolute_time() > wake_deadline) {\n"
         "            kprintf(\"ST59 GICR wake timeout\\n\");\n"
         "            return;\n"
         "        }\n"
         "    }\n"
         "    gicr_write32(GICR_IGROUPR0, 0xFFFFFFFFU);\n", "wait-for-redistributor-wake"),
        ("    gicr_write32(GICR_ISENABLER0, 1U << SWEET_IPI_SGI);\n",
         "    gicr_write32(GICR_ISENABLER0, 1U << SWEET_IPI_SGI);\n"
         "    __builtin_arm_dsb(DSB_SY);\n"
         "    kprintf(\"ST59 SGI enable readback=0x%x\\n\",\n"
         "        gicr_read32(GICR_ISENABLER0));\n", "rearm-readback"),
    ],
}


def generate(tree):
    out = []
    for rel, changes in EDITS.items():
        old = (tree / rel).read_text(encoding="utf-8")
        new = old
        for before, after, label in changes:
            new = replace_once(new, before, after, f"{rel}:{label}")
        out.append(f"diff --git a/{rel} b/{rel}\n")
        out.extend(difflib.unified_diff(old.splitlines(keepends=True),
                                        new.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(out).encode()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = generate(args.tree)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print("STAGE59_PATCH_GENERATED", args.output, len(result))
