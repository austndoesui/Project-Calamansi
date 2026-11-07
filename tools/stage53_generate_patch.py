#!/usr/bin/env python3
"""Generate Stage53 patch 0090 against files already patched by 0089.

Generate from the temporary XNU source snapshot, not from the user's live
Ubuntu checkout. All substitutions require an exact anchor.
"""

import argparse
import difflib
from pathlib import Path


def change(source: str, old: str, new: str, tag: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"{tag}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def patches(tree: Path) -> list[tuple[str, str, str]]:
    modifications = []

    rel = "pexpert/arm/pe_serial.c"
    old = (tree / rel).read_text()
    new = old
    new = change(new,
        "#define FBCON_SCALE     2\n",
        "#if defined(CACTUS)\n"
        "/* 8x16 glyphs: 90 columns x 90 rows on the 720x1440 panel. */\n"
        "#define FBCON_SCALE     1\n"
        "#else\n"
        "#define FBCON_SCALE     2\n"
        "#endif\n"
        "#if defined(CACTUS)\n"
        "/* Rows [0, 7) always belong to the native Cactarwin status header. */\n"
        "#define FBCON_HEADER_ROWS 7u\n"
        "#endif\n",
        "fbcon-header-config")
    new = change(new,
        "static uint32_t fbcon_cols, fbcon_rows, fbcon_col, fbcon_row;\n",
        "static uint32_t fbcon_cols, fbcon_rows, fbcon_col, fbcon_row;\n"
        "static uint32_t fbcon_log_first_row;\n"
        "static void fbcon_transmit_data(uint8_t c);\n"
        "#if defined(CACTUS)\n"
        "static void\n"
        "fbcon_literal(const char *s)\n"
        "{\n"
        "\twhile (*s) {\n"
        "\t\tfbcon_transmit_data((uint8_t)*s++);\n"
        "\t}\n"
        "}\n"
        "#endif\n",
        "fbcon-header-writer")
    new = change(new,
        "\tfbcon_row = (fbcon_row + 1) % fbcon_rows;\n"
        "\tfbcon_clear_row(fbcon_row);\n"
        "\tfbcon_clear_row((fbcon_row + 1) % fbcon_rows);",
        "\tfbcon_row++;\n"
        "\tif (fbcon_row >= fbcon_rows) {\n"
        "\t\tfbcon_row = fbcon_log_first_row;\n"
        "\t}\n"
        "\tfbcon_clear_row(fbcon_row);\n"
        "\tuint32_t next_row = fbcon_row + 1;\n"
        "\tif (next_row >= fbcon_rows) {\n"
        "\t\tnext_row = fbcon_log_first_row;\n"
        "\t}\n"
        "\tfbcon_clear_row(next_row);",
        "fbcon-ring")
    new = change(new,
        "\tfbcon_cols = fbcon_width / (8 * FBCON_SCALE);\n"
        "\tfbcon_rows = fbcon_height / (16 * FBCON_SCALE);\n"
        "\tfbcon_col = fbcon_row = 0;\n"
        "\tfor (uint32_t r = 0; r < fbcon_rows; r++) {\n"
        "\t\tfbcon_clear_row(r);\n"
        "\t}\n",
        "\tfbcon_cols = fbcon_width / (8 * FBCON_SCALE);\n"
        "\tfbcon_rows = fbcon_height / (16 * FBCON_SCALE);\n"
        "\tfbcon_col = fbcon_row = 0;\n"
        "\tfbcon_log_first_row = 0;\n"
        "\tfor (uint32_t r = 0; r < fbcon_rows; r++) {\n"
        "\t\tfbcon_clear_row(r);\n"
        "\t}\n"
        "#if defined(CACTUS)\n"
        "\tif (fbcon_rows > FBCON_HEADER_ROWS + 4) {\n"
        "\t\tfbcon_literal(\"=== [ Cactarwin / Cactus-XNU ] ===\\n\");\n"
        "\t\tfbcon_literal(\"PROJECT  Cactarwin (cactus-xnu)\\n\");\n"
        "\t\tfbcon_literal(\"DEVICE   Xiaomi Redmi 6A (cactus)\\n\");\n"
        "\t\tfbcon_literal(\"DISPLAY  720x1440 framebuffer\\n\");\n"
        "\t\tfbcon_literal(\"--------------------------------\\n\");\n"
        "\t\tfbcon_literal(\"STATUS   Native XNU startup\\n\");\n"
        "\t\tfbcon_literal(\"--------------------------------\\n\");\n"
        "\t\tfbcon_log_first_row = FBCON_HEADER_ROWS;\n"
        "\t\tfbcon_col = 0;\n"
        "\t\tfbcon_row = FBCON_HEADER_ROWS;\n"
        "\t\tfbcon_clear_row(fbcon_row);\n"
        "\t}\n"
        "#endif\n",
        "fbcon-banner")
    mark = '''#if defined(CACTUS)
/*
 * Update the fixed status line without allocating, printing or taking a
 * lock. Called during single-CPU kernel bringup before threaded logging.
 * Restores the scroll cursor so normal output continues uninterrupted.
 */
void
fbcon_stage53_progress(const char *message)
{
    if (fbcon_base == NULL || fbcon_log_first_row != FBCON_HEADER_ROWS) {
        return;
    }
    const uint32_t old_row = fbcon_row, old_col = fbcon_col;
    fbcon_row = FBCON_HEADER_ROWS - 2;
    fbcon_col = 0;
    fbcon_clear_row(fbcon_row);
    fbcon_literal("STATUS   ");
    while (*message && fbcon_col < fbcon_cols) {
        fbcon_transmit_data((uint8_t)*message++);
    }
    fbcon_row = old_row;
    fbcon_col = old_col;
}
#endif

'''
    new = change(new,
        "static unsigned int\nfbcon_receive_ready(void)\n",
        mark + "static unsigned int\nfbcon_receive_ready(void)\n",
        "fbcon-live-status")
    modifications.append((rel, old, new))

    rel = "osfmk/kern/startup.c"
    old = (tree / rel).read_text()
    new = change(old,
        'TUNABLE(startup_debug_t, startup_debug, "startup_debug", 0);',
        '#if defined(CACTUS)\n'
        '/* Print every XNU startup phase, hook, and bootstrap operation. */\n'
        'TUNABLE(startup_debug_t, startup_debug, "startup_debug", STARTUP_DEBUG_VERBOSE);\n'
        'extern void fbcon_stage53_progress(const char *message);\n'
        '#else\n'
        'TUNABLE(startup_debug_t, startup_debug, "startup_debug", 0);\n'
        '#endif',
        "startup-debug")
    new = change(new,
        "kernel_bootstrap_log(const char *message)\n{\n",
        "kernel_bootstrap_log(const char *message)\n{\n"
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(message);\n"
        "#endif\n",
        "bootstrap-header")
    new = change(new,
        "kernel_bootstrap_thread_log(const char *message)\n{\n",
        "kernel_bootstrap_thread_log(const char *message)\n{\n"
        "#if defined(CACTUS)\n"
        "\tfbcon_stage53_progress(message);\n"
        "#endif\n",
        "thread-header")
    new = change(new,
        "\tkernel_startup_initialize_upto(STARTUP_SUB_MACH_IPC);\n",
        "\tkernel_startup_initialize_upto(STARTUP_SUB_MACH_IPC);\n"
        "\tkernel_bootstrap_log(\"MACH_IPC complete\");\n",
        "mach-ipc-finish")
    new = change(new,
        '\tkernel_bootstrap_log("load_context - done");\n\tload_context(thread);',
        '\tkernel_bootstrap_log("load_context enter");\n\tload_context(thread);',
        "load-context-enter")
    new = change(new,
        "\tkernel_startup_initialize_upto(STARTUP_SUB_THREAD_CALL);\n",
        "\tkernel_startup_initialize_upto(STARTUP_SUB_THREAD_CALL);\n"
        "\tkernel_bootstrap_thread_log(\"THREAD_CALL complete\");\n",
        "thread-call-finish")
    new = change(new,
        "\tkernel_startup_initialize_upto(STARTUP_SUB_SYSCTL);\n",
        "\tkernel_startup_initialize_upto(STARTUP_SUB_SYSCTL);\n"
        "\tkernel_bootstrap_thread_log(\"SYSCTL complete\");\n",
        "sysctl-finish")
    new = change(new,
        "\tkernel_startup_initialize_upto(STARTUP_SUB_EARLY_BOOT);\n",
        "\tkernel_startup_initialize_upto(STARTUP_SUB_EARLY_BOOT);\n"
        "\tkernel_bootstrap_thread_log(\"EARLY_BOOT complete\");\n",
        "early-boot-finish")
    new = change(new,
        "#ifdef  MACH_BSD\n\tbsd_init();\n#endif",
        "#ifdef  MACH_BSD\n"
        "\tkernel_bootstrap_thread_log(\"bsd_init enter\");\n"
        "\tbsd_init();\n"
        "\tkernel_bootstrap_thread_log(\"bsd_init returned\");\n"
        "#endif",
        "bsd-call")
    modifications.append((rel, old, new))

    rel = "bsd/kern/bsd_init.c"
    old = (tree / rel).read_text()
    new = change(old, "#define DEBUG_BSDINIT 0",
        "#if defined(CACTUS)\n#define DEBUG_BSDINIT 1\n"
        "#else\n#define DEBUG_BSDINIT 0\n#endif",
        "bsd-verbose")
    new = change(new,
        "\tthrottle_init();\n\n\tprintf(copyright);",
        "#if defined(CACTUS)\n"
        "\textern void fbcon_stage53_progress(const char *);\n"
        "\tfbcon_stage53_progress(\"bsd_init: throttle_init\");\n"
        "#endif\n"
        "\tthrottle_init();\n\n\tprintf(copyright);",
        "bsd-entry")
    new = change(new,
        '\tbsd_init_kprintf("calling bsd_utaskbootstrap\\n");\n\tbsd_utaskbootstrap();',
        '\tbsd_init_kprintf("calling bsd_utaskbootstrap\\n");\n'
        '#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("bsd_utaskbootstrap enter");\n'
        '#endif\n'
        '\tbsd_utaskbootstrap();\n'
        '#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("bsd_utaskbootstrap done");\n'
        '#endif',
        "bsd-utask-bootstrap")
    new = change(new,
        '\tbsd_init_kprintf("done\\n");',
        '#if defined(CACTUS)\n'
        '\tfbcon_stage53_progress("bsd_init complete");\n'
        '#endif\n'
        '\tbsd_init_kprintf("done\\n");',
        "bsd-done")
    modifications.append((rel, old, new))

    rel = "osfmk/arm64/sweet_early.c"
    old = (tree / rel).read_text()
    new = change(old,
        "\tif (stage == 20) {\n\t\tcactus_stage52_banner();\n\t}",
        "\t/* Once the native fbcon owns layer1 (after serial_init),\n"
        "\t * reserve its header and log rows. Early panic stays active. */\n"
        "\tif (stage >= 19) {\n"
        "\t\treturn;\n"
        "\t}",
        "early-to-native-owner")
    modifications.append((rel, old, new))
    return modifications


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    diff = []
    for rel, orig, mod in patches(args.tree):
        diff.append(f"diff --git a/{rel} b/{rel}\n")
        diff.extend(difflib.unified_diff(orig.splitlines(keepends=True),
                                         mod.splitlines(keepends=True),
                                         fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(diff))
    print("STAGE53_PATCH_GENERATED", args.output, args.output.stat().st_size)


if __name__ == "__main__":
    main()
