#!/usr/bin/env python3
"""Stage58: audited GICv3 SGI delivery snapshot and bounded CPU0 rearm.

Reads isolated XNU Stage57 source with patches 0093+0094 applied. Emits an
additive patch. Never edits sources or changes CPU-ready/signal semantics.
"""
import argparse
import difflib
from pathlib import Path


def replace_one(source, old, new, key):
    n = source.count(old)
    if n != 1:
        raise ValueError(f"{key}: expected one match, got {n}")
    return source.replace(old, new)


GIC_DEBUG = r'''
#if defined(CACTUS)
/* Snapshot deliberately avoids ICC_IAR1: reading that register ACKs an IRQ.
 * Bits 0..7 are failure conditions; bit 8 says SGI1 is pending in GICR;
 * bits 32..43 carry the non-acknowledging highest pending INTID. */
uint64_t
cactus_gicv3_cpu0_snapshot(void)
{
    if (!gicd_base || !gicr_base) {
        return 1ULL << 63;
    }
    vm_offset_t gicr_pe_base = find_gicr_pe_base();
    uint64_t status = 0;
    uint64_t daif = __builtin_arm_rsr64("DAIF");
    uint64_t igrpen = __builtin_arm_rsr64("ICC_IGRPEN1_EL1");
    uint64_t pmr = __builtin_arm_rsr64("ICC_PMR_EL1");
    uint64_t sre = __builtin_arm_rsr64("ICC_SRE_EL1");
    uint64_t hppir = __builtin_arm_rsr64("ICC_HPPIR1_EL1") & 0xFFFULL;
    uint32_t waker = gicr_read32(GICR_WAKER);
    uint32_t enabled = gicr_read32(GICR_ISENABLER0);
    uint32_t pending = gicr_read32(0x10200); /* GICR_ISPENDR0 */
    uint32_t dctlr = gicd_read32(GICD_CTLR);
    if (daif & (1ULL << 7)) status |= 1ULL << 0; /* DAIF.I */
    if (!(igrpen & 1)) status |= 1ULL << 1;
    if (pmr <= 0xA0) status |= 1ULL << 2;
    if (!(sre & ICC_SRE_SRE)) status |= 1ULL << 3;
    if (!(dctlr & (GICD_CTLR_ENABLEGRP1A | GICD_CTLR_ENABLEGRP1))) status |= 1ULL << 4;
    if (waker & GICR_WAKER_CHILDRENASLEEP) status |= 1ULL << 5;
    if (!(enabled & (1U << SWEET_IPI_SGI))) status |= 1ULL << 6;
    if (pending & (1U << SWEET_IPI_SGI)) status |= 1ULL << 8;
    if (hppir == SWEET_IPI_SGI) status |= 1ULL << 9;
    return status | (hppir << 32);
}

/* Re-establish the GICv3 Group-1 NS SGI path on the already-initialized
 * bootstrap CPU only. Do not change DAIF, other interrupt priorities,
 * SIGPdisabled, CPU state, or interrupt-context locking. */
void
cactus_gicv3_cpu0_rearm(void)
{
    if (!gicd_base || !gicr_base) {
        return;
    }
    vm_offset_t gicr_pe_base = find_gicr_pe_base();
    if (gicr_read32(GICR_WAKER) & GICR_WAKER_PROCESSORSLEEP) {
        gicr_write32(GICR_WAKER,
            gicr_read32(GICR_WAKER) & ~GICR_WAKER_PROCESSORSLEEP);
    }
    gicr_write32(GICR_IGROUPR0, 0xFFFFFFFFU);
    gicr_write32(GICR_ISENABLER0, 1U << SWEET_IPI_SGI);
    if (!(__builtin_arm_rsr64("ICC_SRE_EL1") & ICC_SRE_SRE)) {
        __builtin_arm_wsr64("ICC_SRE_EL1",
            __builtin_arm_rsr64("ICC_SRE_EL1") | ICC_SRE_SRE);
    }
    if (__builtin_arm_rsr64("ICC_PMR_EL1") <= 0xA0) {
        __builtin_arm_wsr64("ICC_PMR_EL1", 0xFF);
    }
    uint32_t ctlr = gicd_read32(GICD_CTLR);
    if (!(ctlr & (GICD_CTLR_ENABLEGRP1A | GICD_CTLR_ENABLEGRP1))) {
        gicd_write32(GICD_CTLR, ctlr | GICD_CTLR_ENABLEGRP1A | GICD_CTLR_ENABLEGRP1);
    }
    if (!(__builtin_arm_rsr64("ICC_IGRPEN1_EL1") & 1)) {
        __builtin_arm_wsr64("ICC_IGRPEN1_EL1", 1);
    }
    __builtin_arm_dsb(DSB_SY);
    __builtin_arm_isb(ISB_SY);
}
#endif
'''

def generate(tree):
    edits = {
        "pexpert/arm/pe_fiq.c": [
            ('\n#else\nvoid\npe_init_fiq()\n{\n}\n#endif\n',
             GIC_DEBUG + '\n#else\nvoid\npe_init_fiq()\n{\n}\n#endif\n', 'GIC-helper'),
        ],
        "iokit/Kernel/arm/SweetCPU.cpp": [
            ('extern "C" volatile unsigned int cactus_sgi_observed;\n',
             'extern "C" volatile unsigned int cactus_sgi_observed;\n'
             'extern "C" uint64_t cactus_gicv3_cpu0_snapshot(void);\n'
             'extern "C" void cactus_gicv3_cpu0_rearm(void);\n', 'GIC-helper-externs'),
            ('\t\tbool noted_init = false, noted_sgi = false, noted_delivery = false;\n',
             '\t\tbool noted_init = false, noted_sgi = false, noted_delivery = false;\n'
             '\t\tbool noted_gic = false;\n', 'flag'),
            ('\t\t\tuint64_t now = mach_absolute_time();\n',
             '\t\t\tif (i == topology->boot_cpu->cpu_id && initialized &&\n'
             '\t\t\t    !signal_ready && !noted_gic) {\n'
             '\t\t\t\tuint64_t state = cactus_gicv3_cpu0_snapshot();\n'
             '\t\t\t\tIOLog("CACTUS GICv3 pre-rearm status=0x%llx irq_seen=%u\\n",\n'
             '\t\t\t\t    (unsigned long long)state, seen);\n'
             '\t\t\t\tfbcon_stage53_progress((state & 1) ? "ST58 CPU0 IRQ MASKED" :\n'
             '\t\t\t\t    (state & 2) ? "ST58 GIC CPU1 OFF" :\n'
             '\t\t\t\t    (state & 4) ? "ST58 GIC PMR BLOCK" :\n'
             '\t\t\t\t    (state & 0x20) ? "ST58 REDIST ASLEEP" :\n'
             '\t\t\t\t    (state & 0x40) ? "ST58 SGI1 DISABLED" :\n'
             '\t\t\t\t    (state & 0x100) ? "ST58 SGI1 PENDING" :\n'
             '\t\t\t\t    "ST58 SGI1 NOT PENDING");\n'
             '\t\t\t\tnoted_gic = true;\n'
             '\t\t\t}\n'
             '\t\t\tuint64_t now = mach_absolute_time();\n', 'status-in-loop'),
            ('\t\t\t\tpanic("CACTUS CPU%u readiness timeout (init/IRQ/SGI)", i);\n',
             '\t\t\t\tif (i == topology->boot_cpu->cpu_id) {\n'
             '\t\t\t\t\tuint64_t state = cactus_gicv3_cpu0_snapshot();\n'
             '\t\t\t\t\tIOLog("CACTUS GICv3 timeout status=0x%llx IRQs=%u\\n",\n'
             '\t\t\t\t\t    (unsigned long long)state, seen);\n'
             '\t\t\t\t\tfbcon_stage53_progress((state & 1) ? "ST58 TIMEOUT IRQ MASK" :\n'
             '\t\t\t\t\t    (state & 0x100) ? "ST58 TIMEOUT SGI PENDING" :\n'
             '\t\t\t\t\t    seen ? "ST58 TIMEOUT SIGNAL FLAG" :\n'
             '\t\t\t\t\t    "ST58 TIMEOUT SGI ABSENT");\n'
             '\t\t\t\t}\n'
             '\t\t\t\tpanic("CACTUS CPU%u readiness timeout (init/IRQ/SGI)", i);\n', 'timeout-status'),
            ('\t\t\t\tfbcon_stage53_progress("ST57 CPU0 resend SGI");\n'
             '\t\t\t\tcpu->signalCPU(cpu);\n',
             '\t\t\t\tfbcon_stage53_progress("ST58 GICv3 rearm SGI1");\n'
             '\t\t\t\tcactus_gicv3_cpu0_rearm();\n'
             '\t\t\t\tcpu->signalCPU(cpu);\n'
             '\t\t\t\tfbcon_stage53_progress("ST58 CPU0 SGI1 retried");\n', 'rearm'),
        ],
    }
    out = []
    for rel, changes in edits.items():
        before = (tree / rel).read_text(encoding='utf-8')
        after = before
        for old, new, tag in changes:
            after = replace_one(after, old, new, f'{rel}:{tag}')
        out.append(f'diff --git a/{rel} b/{rel}\n')
        out.extend(difflib.unified_diff(before.splitlines(keepends=True),
                                        after.splitlines(keepends=True),
                                        fromfile=f'a/{rel}', tofile=f'b/{rel}'))
    return ''.join(out).encode('utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    patch = generate(args.tree)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    print('STAGE58_PATCH_GENERATED', args.output, 'bytes', len(patch))
