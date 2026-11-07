#!/usr/bin/env python3
"""Generate the ordered Stage52 XNU patch against the Stage51-patched tree.

Does not modify the WSL source checkout. A fresh CI run applies the
generated patch *after* 0088, keeping all original Stage51 assets intact.
"""
import argparse
import difflib
from pathlib import Path


def exactly(source: str, old: str, new: str, label: str) -> str:
    hits = source.count(old)
    if hits != 1:
        raise ValueError(f"{label}: expected one occurrence, found {hits}")
    return source.replace(old, new, 1)


def instrument(tree: Path) -> list[tuple[str, str, str]]:
    modified = []
    rel = "osfmk/arm64/sweet_early.c"
    original = (tree / rel).read_text()
    updated = original
    banner = """
#if defined(CACTUS)
/*
 * Draw only confirmed facts here. LK boot state, CPU count and GIC readiness
 * must not be fabricated. No dynamic allocation, locks or external console.
 */
static void
cactus_stage52_banner(void)
{
    sweet_early_string("\\n=== [ Cactarwin / Cactus-XNU ] ===\\n");
    sweet_early_string("PROJECT  Cactarwin (cactus-xnu)\\n");
    sweet_early_string("DEVICE   Xiaomi Redmi 6A (cactus)\\n");
    sweet_early_string("DISPLAY  LK layer1 720x1440\\n");
    sweet_early_string("STATUS   Native XNU startup\\n");
    sweet_early_string("LOADER   XNU Mach-O accepted\\n");
    sweet_early_string("--------------------------------\\n");
}
#endif
"""
    anchor = "\nvoid\nsweet_early_mark(unsigned int stage, const char *label)\n"
    updated = exactly(updated, anchor, banner + anchor, rel + ":banner")
    updated = exactly(
        updated,
        "if (early_disabled || stage > 20) {",
        "#if defined(CACTUS)\n\tif (early_disabled || stage > 99) {\n#else\n\tif (early_disabled || stage > 20) {\n#endif",
        rel + ":stage-limit",
    )
    updated = exactly(
        updated,
        "\tuint32_t color = 0xff00ff00u",
        "#if defined(CACTUS)\n\tif (stage == 20) {\n\t\tcactus_stage52_banner();\n\t}\n#endif\n\tuint32_t color = 0xff00ff00u",
        rel + ":draw",
    )
    updated = exactly(updated, 'sweet_early_string("CACTUS-XNU-STAGE51 ");',
                      'sweet_early_string("CACTUS-XNU-STAGE52 ");', rel + ":stage-string")
    updated = exactly(updated, 'sweet_early_string("\\nCACTUS-XNU-STAGE51 PANIC: ");',
                      'sweet_early_string("\\nCACTUS-XNU-STAGE52 PANIC: ");', rel + ":panic-string")
    modified.append((rel, original, updated))

    rel = "osfmk/arm/arm_init.c"
    original = (tree / rel).read_text()
    updated = original
    updated = exactly(
        updated,
        '\tsweet_early_mark(20, "kprintf startup complete");\n\tif (serial_exists) {\n\t\tsweet_early_disable();\n\t}',
        '''\tsweet_early_mark(20, "kprintf startup complete");
\t/* Cactus: keep the guaranteed early framebuffer console alive after
\t * serial registration, including during native panic paths. */
#if !defined(CACTUS)
\tif (serial_exists) {
\t\tsweet_early_disable();
\t}
#endif
\tsweet_early_mark(21, "serial mode setup");''',
        rel + ":console-lifetime",
    )
    updated = exactly(
        updated,
        '''\tif (kern_feature_override(KF_SERIAL_OVRD)) {
\t\tserialmode = 0;
\t}
''',
        '''\tif (kern_feature_override(KF_SERIAL_OVRD)) {
\t\tserialmode = 0;
\t}
#if defined(CACTUS)
\t/* The framebuffer is the only viable Cactus text output. Keep native
\t * kprintf routed to its registered serial framebuffer backend. */
\tif (serial_exists) {
\t\tserialmode |= SERIALMODE_OUTPUT;
\t}
#endif
\tsweet_early_mark(22, "switching native console");
''',
        rel + ":serial-enable",
    )
    updated = exactly(
        updated,
        '\tPE_create_console();\n\n\t/* setup console output */\n\tPE_init_printf(FALSE);',
        '''\tsweet_early_mark(23, "serial output selected");
\tPE_create_console();
\tsweet_early_mark(24, "PE_create_console done");

\t/* setup console output */
\tPE_init_printf(FALSE);
\tsweet_early_mark(25, "PE_init_printf done");''',
        rel + ":console-ready",
    )
    updated = exactly(updated,
        '\tcpu_machine_idle_init(TRUE);\n\n\tPE_init_platform(TRUE, &BootCpuData);',
        '''\tsweet_early_mark(26, "cpu_machine_idle_init enter");
\tcpu_machine_idle_init(TRUE);
\tsweet_early_mark(27, "cpu_machine_idle_init done");

\tPE_init_platform(TRUE, &BootCpuData);
\tsweet_early_mark(28, "PE_init_platform late done");''',
        rel + ":idle",
    )
    updated = exactly(updated, '\tml_map_cpu_pio();',
        '\tsweet_early_mark(29, "ml_map_cpu_pio enter");\n\tml_map_cpu_pio();\n\tsweet_early_mark(30, "ml_map_cpu_pio returned");',
        rel + ":pio",
    )
    updated = exactly(updated, '\tcpu_timebase_init(TRUE);',
        '\tsweet_early_mark(31, "cpu_timebase_init enter");\n\tcpu_timebase_init(TRUE);\n\tsweet_early_mark(32, "cpu_timebase_init done");',
        rel + ":timebase",
    )
    updated = exactly(updated, '\tPE_init_cpu();\n\tfiq_context_init(TRUE);',
        '''\tsweet_early_mark(33, "PE_init_cpu enter");
\tPE_init_cpu();
\tsweet_early_mark(34, "PE_init_cpu done");
\tfiq_context_init(TRUE);
\tsweet_early_mark(35, "fiq_context_init done");''',
        rel + ":cpu",
    )
    updated = exactly(updated, '\tgDramBase = *dram_base;\n\tgDramSize = *dram_size;',
        '\tgDramBase = *dram_base;\n\tgDramSize = *dram_size;\n\tsweet_early_mark(36, "chosen DRAM parsed");',
        rel + ":chosen-DRAM",
    )
    updated = exactly(updated, '\tmachine_startup(args);',
        '\tsweet_early_mark(37, "machine_startup enter");\n\tmachine_startup(args);',
        rel + ":handoff",
    )
    modified.append((rel, original, updated))
    return modified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage51_source_tree", type=Path)
    parser.add_argument("output_patch", type=Path)
    args = parser.parse_args()
    diffs = []
    for rel, before, after in instrument(args.stage51_source_tree):
        chunk = list(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}", n=5))
        if not chunk:
            raise ValueError(f"{rel}: generated empty changes")
        diffs.append(f"diff --git a/{rel} b/{rel}\n" + "".join(chunk))
    args.output_patch.parent.mkdir(parents=True, exist_ok=True)
    args.output_patch.write_text("".join(diffs))
    print("STAGE52_KERNEL_PATCH_GENERATED", args.output_patch,
          "bytes", args.output_patch.stat().st_size)


if __name__ == "__main__":
    main()
