#!/usr/bin/env python3
"""Generate the additive Cactus Stage55 BSD-gate patch after Stage54 patch 0091.

The source tree argument must have all patches through 0091 applied. Exact
single-context substitutions reject drift; unrelated XNU sources stay intact.
"""
import argparse
import difflib
from pathlib import Path


def replace_once(source: str, old: str, new: str, name: str) -> str:
    n = source.count(old)
    if n != 1:
        raise ValueError(f"{name}: expected 1 occurrence, found {n}")
    return source.replace(old, new, 1)


def generate(tree: Path) -> str:
    changed = []
    rel = "osfmk/kern/startup.c"
    old = (tree / rel).read_text(encoding="utf-8")
    new = replace_once(
        old,
        "#if KPERF\n\tkperf_init_early();\n#endif\n\n\t/*\n\t *\tStart the user bootstrap.\n",
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(\"ST55 after VM restrictions\");\n"
        "#endif\n"
        "#if KPERF\n"
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(\"ST55 KPERF early enter\");\n"
        "#endif\n"
        "\tkperf_init_early();\n"
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(\"ST55 KPERF early done\");\n"
        "#endif\n"
        "#else\n"
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(\"ST55 KPERF disabled\");\n"
        "#endif\n"
        "#endif\n"
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(\"ST55 before MACH_BSD gate\");\n"
        "#endif\n\n"
        "\t/*\n\t *\tStart the user bootstrap.\n",
        "kperf-or-bsd-boundary",
    )
    new = replace_once(
        new,
        '#ifdef  MACH_BSD\n#if defined(CACTUS)\n'
        '\tkernel_bootstrap_thread_log("ST54 BSD entry boundary");\n',
        '#ifdef  MACH_BSD\n#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("ST55 MACH_BSD enabled");\n'
        '\tkernel_bootstrap_thread_log("ST54 BSD entry boundary");\n',
        "bsd-config-confirmation",
    )
    new = replace_once(
        new,
        '\tkernel_bootstrap_thread_log("bsd_init returned");\n#endif\n',
        '\tkernel_bootstrap_thread_log("bsd_init returned");\n'
        '#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("ST55 bsd_init returned");\n'
        '#endif\n'
        '#else\n'
        '#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("ST55 MACH_BSD disabled");\n'
        '#endif\n'
        '#endif\n',
        "bsd-configuration-fallback",
    )
    changed.append((rel, old, new))

    rel = "bsd/kern/bsd_init.c"
    old = (tree / rel).read_text(encoding="utf-8")
    new = replace_once(
        old,
        '#if (DEVELOPMENT || DEBUG)\n'
        '\tplatform_stall_panic_or_spin(PLATFORM_STALL_XNU_LOCATION_BSD_INIT);\n',
        '#if defined(CACTUS)\n'
        '\textern void fbcon_stage53_progress(const char *);\n'
        '\tfbcon_stage53_progress("ST55 bsd_init first instruction");\n'
        '#endif\n'
        '#if (DEVELOPMENT || DEBUG)\n'
        '\tplatform_stall_panic_or_spin(PLATFORM_STALL_XNU_LOCATION_BSD_INIT);\n',
        "bsd-first-statement",
    )
    new = replace_once(
        new,
        '\tthrottle_init();\n\n\tprintf(copyright);\n',
        '\tthrottle_init();\n'
        '#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("ST55 bsd throttle complete");\n'
        '#endif\n\n\tprintf(copyright);\n',
        "bsd-throttle-return",
    )
    changed.append((rel, old, new))

    out = []
    for rel, before, after in changed:
        out.append(f"diff --git a/{rel} b/{rel}\n")
        out.extend(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}",
        ))
    return "".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    patch = generate(args.tree)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch.encode("utf-8"))
    print("STAGE55_PATCH_GENERATED", args.output, len(patch))
