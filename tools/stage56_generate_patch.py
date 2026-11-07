#!/usr/bin/env python3
"""Generate the narrowly scoped Stage56 CPU synchronization diagnostics.

Input is a snapshot of the XNU sources *before* patch 0093; substitutions
are exact and fail closed. The patch leaves the CPU completion contract intact.
"""
import argparse
import difflib
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"{label}: wanted 1 occurrence, found {text.count(old)}")
    return text.replace(old, new)


def generate(root: Path) -> bytes:
    diff = []
    edits = {
        "osfmk/kperf/kperf.c": [
            ("\tml_wait_max_cpus();\n",
             '#if defined(CACTUS)\n'
             '\textern void fbcon_stage53_progress(const char *);\n'
             '\tfbcon_stage53_progress("ST56 CPU wait enter");\n'
             '#endif\n'
             '\tml_wait_max_cpus();\n'
             '#if defined(CACTUS)\n'
             '\tfbcon_stage53_progress("ST56 CPU wait done");\n'
             '#endif\n', "kperf-wait"),
        ],
        "osfmk/arm/machine_routines_common.c": [
            ("void\nml_set_max_cpus(unsigned int max_cpus __unused)\n{\n",
             "void\nml_set_max_cpus(unsigned int max_cpus __unused)\n{\n"
             '#if defined(CACTUS)\n'
             '\textern void fbcon_stage53_progress(const char *);\n'
             '\tfbcon_stage53_progress("ST56 CPU publish enter");\n'
             '#endif\n', "publish-enter"),
            ("\tlck_mtx_unlock(&max_cpus_lock);\n}\n\nunsigned int\nml_wait_max_cpus(void)",
             '\tlck_mtx_unlock(&max_cpus_lock);\n'
             '#if defined(CACTUS)\n'
             '\tfbcon_stage53_progress("ST56 CPU publish done");\n'
             '#endif\n'
             '}\n\nunsigned int\nml_wait_max_cpus(void)', "publish-done"),
            ("\twhile (max_cpus_initialized != MAX_CPUS_SET) {\n\t\tmax_cpus_initialized = MAX_CPUS_WAIT;\n",
             '\twhile (max_cpus_initialized != MAX_CPUS_SET) {\n'
             '#if defined(CACTUS)\n'
             '\t\tfbcon_stage53_progress("ST56 CPU wait sleeping");\n'
             '#endif\n'
             '\t\tmax_cpus_initialized = MAX_CPUS_WAIT;\n', "wait-sleep"),
        ],
        "iokit/Kernel/arm/SweetCPU.cpp": [
            ('/* Do not wait in a nub\'s start(): matching can be asynchronous or serialized. */\n',
             '#if defined(CACTUS)\n'
             'extern "C" void fbcon_stage53_progress(const char *);\n'
             '#endif\n'
             '/* Do not wait in a nub\'s start(): matching can be asynchronous or serialized. */\n',
             "cxx-linkage"),
            ('\tIOLog("SWEET CPU: requested=%u selected=%u (limit=%u)\\n",\n'
             '\t    requested, topology->num_cpus, SWEET_SMP_MAX_CPUS);\n',
             '\tIOLog("SWEET CPU: requested=%u selected=%u (limit=%u)\\n",\n'
             '\t    requested, topology->num_cpus, SWEET_SMP_MAX_CPUS);\n'
             '#if defined(CACTUS)\n'
             '\tfbcon_stage53_progress("ST56 CPU startAll enter");\n'
             '#endif\n', "startall-enter"),
            ('\t/* The supplied ADT has cpu0 as the boot CPU and ascending A55 nodes. */\n',
             '#if defined(CACTUS)\n'
             '\tfbcon_stage53_progress("ST56 CPU registered all");\n'
             '#endif\n'
             '\t/* The supplied ADT has cpu0 as the boot CPU and ascending A55 nodes. */\n', "registration-done"),
            ('\t\tSweetCPU *cpu = __atomic_load_n(&sweet_cpus[i], __ATOMIC_ACQUIRE);\n'
             '\t\tkern_return_t kr = processor_start(cpu->machProcessor);\n',
             '\t\tSweetCPU *cpu = __atomic_load_n(&sweet_cpus[i], __ATOMIC_ACQUIRE);\n'
             '#if defined(CACTUS)\n'
             '\t\tfbcon_stage53_progress("ST56 CPU processor_start enter");\n'
             '#endif\n'
             '\t\tkern_return_t kr = processor_start(cpu->machProcessor);\n', "processor-start"),
            ('\t\t/* processor_start() is asynchronous for secondaries in this XNU. */\n',
             '#if defined(CACTUS)\n'
             '\t\tfbcon_stage53_progress("ST56 CPU processor_start done");\n'
             '#endif\n'
             '\t\t/* processor_start() is asynchronous for secondaries in this XNU. */\n', "processor-return"),
            ('\t\tIOLog("SWEET CPU: cpu=%u mpidr=0x%x came alive; SGI1 OK\\n",\n'
             '\t\t    i, topology->cpus[i].phys_id);\n',
             '\t\tIOLog("SWEET CPU: cpu=%u mpidr=0x%x came alive; SGI1 OK\\n",\n'
             '\t\t    i, topology->cpus[i].phys_id);\n'
             '#if defined(CACTUS)\n'
             '\t\tfbcon_stage53_progress("ST56 CPU ready and SGI OK");\n'
             '#endif\n', "cpu-ready"),
            ('\t/* Publish exactly once, after every selected CPU has completed initCPU(). */\n',
             '#if defined(CACTUS)\n'
             '\tfbcon_stage53_progress("ST56 CPU before publish");\n'
             '#endif\n'
             '\t/* Publish exactly once, after every selected CPU has completed initCPU(). */\n', "publish-begin"),
            ('\tml_set_max_cpus(topology->max_cpu_id + 1);\n',
             '\tml_set_max_cpus(topology->max_cpu_id + 1);\n'
             '#if defined(CACTUS)\n'
             '\tfbcon_stage53_progress("ST56 CPU all initialized");\n'
             '#endif\n', "publish-end"),
        ],
    }
    for rel, changes in edits.items():
        before = (root / rel).read_text(encoding="utf-8")
        after = before
        for old, new, label in changes:
            after = once(after, old, new, f"{rel}:{label}")
        diff.append(f"diff --git a/{rel} b/{rel}\n")
        diff.extend(difflib.unified_diff(before.splitlines(keepends=True),
                                         after.splitlines(keepends=True),
                                         fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(diff).encode("utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = generate(args.tree)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)
    print("STAGE56_PATCH_GENERATED", args.output, "bytes", len(out))
