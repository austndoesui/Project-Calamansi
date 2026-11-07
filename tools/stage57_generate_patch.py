#!/usr/bin/env python3
"""Generate additive Stage57 CPU0 SGI readiness/retry source patch.

Input source snapshot has the Stage56 (0093) patch applied. No changes are
made to the input or the user's XNU checkout. Matches must be unambiguous.
"""
import argparse
import difflib
from pathlib import Path


def substitute(data: str, old: str, new: str, desc: str) -> str:
    found = data.count(old)
    if found != 1:
        raise ValueError(f"{desc}: expected exactly one match, found {found}")
    return data.replace(old, new)


def generate(root: Path) -> bytes:
    edits = {
        "osfmk/arm64/sleh.c": [
            ("void\nsleh_irq(arm_saved_state_t *state)\n{\n",
             "#if defined(CACTUS)\n"
             "/* IRQ observer; read by the CPU startup thread, never a control bit. */\n"
             "volatile unsigned int cactus_sgi_observed;\n"
             "#endif\n"
             "void\nsleh_irq(arm_saved_state_t *state)\n{\n", "sgi-observer"),
            ("\t} else if (intid < 16) {\n\t\tsleh_interrupt_handler_prologue(state, DBG_INTR_TYPE_IPI);\n",
             "\t} else if (intid < 16) {\n"
             "#if defined(CACTUS)\n"
             "\t\tif (intid == SWEET_IPI_SGI) {\n"
             "\t\t\t__atomic_add_fetch(&cactus_sgi_observed, 1U, __ATOMIC_RELAXED);\n"
             "\t\t}\n"
             "#endif\n"
             "\t\tsleh_interrupt_handler_prologue(state, DBG_INTR_TYPE_IPI);\n", "sgi-handler"),
        ],
        "iokit/Kernel/arm/SweetCPU.cpp": [
            ('extern "C" void fbcon_stage53_progress(const char *);\n',
             'extern "C" void fbcon_stage53_progress(const char *);\n'
             'extern "C" volatile unsigned int cactus_sgi_observed;\n', "observer-linkage"),
            ("\t\t/* processor_start() is asynchronous for secondaries in this XNU. */\n"
             "\t\tnanoseconds_to_deadline(5 * NSEC_PER_SEC, &deadline);\n"
             "\t\twhile (__atomic_load_n(&cpu->initialized, __ATOMIC_ACQUIRE) == 0 ||\n"
             "\t\t    !sweet_cpu_signal_is_enabled(i)) {\n"
             "\t\t\tif (mach_absolute_time() > deadline) {\n"
             "\t\t\t\tIOLog(\"SWEET CPU: cpu=%u mpidr=0x%x NOT alive after 5s\\n\",\n"
             "\t\t\t\t    i, topology->cpus[i].phys_id);\n"
             "\t\t\t\tpanic(\"SWEET CPU: cpu=%u startup timeout (reset/MMU/GIC/SGI)\", i);\n"
             "\t\t\t}\n"
             "\t\t\tIOSleep(1);\n"
             "\t\t}\n",
             "\t\t/* Check CPU initialization and IRQ delivery independently.  A lost\n"
             "\t\t * initial self-SGI can safely be retried once CPU0 is initialized.\n"
             "\t\t * Never fake SIGPdisabled or mark an uninitialized CPU ready. */\n"
             "\t\tnanoseconds_to_deadline(5 * NSEC_PER_SEC, &deadline);\n"
             "\t\tuint64_t retry_at;\n"
             "\t\tnanoseconds_to_deadline(250000000ULL, &retry_at);\n"
             "\t\tunsigned int retries = 0;\n"
             "\t\tbool noted_init = false, noted_sgi = false, noted_delivery = false;\n"
             "\t\tfor (;;) {\n"
             "\t\t\tbool initialized = __atomic_load_n(&cpu->initialized, __ATOMIC_ACQUIRE) != 0;\n"
             "\t\t\tbool signal_ready = sweet_cpu_signal_is_enabled(i);\n"
             "\t\t\tunsigned int seen = __atomic_load_n(&cactus_sgi_observed, __ATOMIC_RELAXED);\n"
             "\t\t\tif (initialized && signal_ready) {\n"
             "\t\t\t\tfbcon_stage53_progress(\"ST57 CPU0 init and IRQ OK\");\n"
             "\t\t\t\tbreak;\n"
             "\t\t\t}\n"
             "\t\t\tif (!initialized && !noted_init) {\n"
             "\t\t\t\tfbcon_stage53_progress(\"ST57 CPU0 init pending\");\n"
             "\t\t\t\tnoted_init = true;\n"
             "\t\t\t} else if (initialized && !signal_ready && !noted_sgi) {\n"
             "\t\t\t\tfbcon_stage53_progress(\"ST57 CPU0 SGI pending\");\n"
             "\t\t\t\tnoted_sgi = true;\n"
             "\t\t\t}\n"
             "\t\t\tif (seen && !noted_delivery) {\n"
             "\t\t\t\tfbcon_stage53_progress(\"ST57 CPU0 SGI IRQ seen\");\n"
             "\t\t\t\tnoted_delivery = true;\n"
             "\t\t\t}\n"
             "\t\t\tuint64_t now = mach_absolute_time();\n"
             "\t\t\tif (now > deadline) {\n"
             "\t\t\t\tfbcon_stage53_progress(!initialized ? \"ST57 CPU0 INIT timeout\" :\n"
             "\t\t\t\t    (!seen ? \"ST57 CPU0 NO SGI timeout\" : \"ST57 CPU0 SIGNAL timeout\"));\n"
             "\t\t\t\tIOLog(\"CACTUS CPU %u: initialized=%u signal_ready=%u sgi_seen=%u retries=%u\\n\",\n"
             "\t\t\t\t    i, initialized, signal_ready, seen, retries);\n"
             "\t\t\t\tpanic(\"CACTUS CPU%u readiness timeout (init/IRQ/SGI)\", i);\n"
             "\t\t\t}\n"
             "\t\t\tif (i == topology->boot_cpu->cpu_id && initialized && !signal_ready &&\n"
             "\t\t\t    retries < 3 && now >= retry_at) {\n"
             "\t\t\t\tfbcon_stage53_progress(\"ST57 CPU0 resend SGI\");\n"
             "\t\t\t\tcpu->signalCPU(cpu);\n"
             "\t\t\t\tretries++;\n"
             "\t\t\t\tnanoseconds_to_deadline(250000000ULL, &retry_at);\n"
             "\t\t\t}\n"
             "\t\t\tIOSleep(1);\n"
             "\t\t}\n", "split-ready-with-retries"),
            ("\tsignalCPU(this);\n\tsetCPUState(kIOCPUStateRunning);\n",
             "#if defined(CACTUS)\n"
             "\tfbcon_stage53_progress(\"ST57 CPU initCPU reached\");\n"
             "#endif\n"
             "\tsignalCPU(this);\n"
             "#if defined(CACTUS)\n"
             "\tfbcon_stage53_progress(\"ST57 CPU self SGI sent\");\n"
             "#endif\n"
             "\tsetCPUState(kIOCPUStateRunning);\n", "cpu-init-entry"),
            ("\t__atomic_store_n(&initialized, 1, __ATOMIC_RELEASE);\n",
             "\t__atomic_store_n(&initialized, 1, __ATOMIC_RELEASE);\n"
             "#if defined(CACTUS)\n"
             "\tfbcon_stage53_progress(\"ST57 CPU initCPU complete\");\n"
             "#endif\n", "cpu-init-exit"),
        ],
    }
    out = []
    for rel, changes in edits.items():
        before = (root / rel).read_text(encoding="utf-8")
        after = before
        for old, new, tag in changes:
            after = substitute(after, old, new, f"{rel}:{tag}")
        out.append(f"diff --git a/{rel} b/{rel}\n")
        out.extend(difflib.unified_diff(before.splitlines(keepends=True),
                                        after.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(out).encode("utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    patch = generate(args.tree)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    print("STAGE57_PATCH_GENERATED", args.output, "bytes", len(patch))
