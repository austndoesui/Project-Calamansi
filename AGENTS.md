# Agent guidelines — Project Calamansi (draft)

## Project scope

Project Calamansi brings the open-source XNU kernel to the **MediaTek MT6761/MT6765 family**. The first hardware-proven port is Xiaomi Redmi 6A (`cactus`); `cph2179` is a separate target. Do not assume hardware behavior proven on cactus applies to another board.

## Start here

1. Read `README.md`, the target device's `devices/<device>/README.md`, and the latest test record for that device. Cactus hardware evidence is in `docs/devices/cactus/`, including Stage79.
2. Inspect `git status`, the current branch and the patch manifest before editing. Keep unrelated user changes untouched.
3. Identify whether a change belongs to shared XNU, the MT6765 platform, a particular device, or the host toolchain. Never infer scope from an old filename alone.
4. State the evidence for hardware claims: local build, offline test, actual fastboot flash, USB handoff, native framebuffer and userspace entry are separate outcomes.

## Proposed ownership boundaries

| Scope | Proposed location | Examples |
| --- | --- | --- |
| Generic kernel | `xnu/patches/common/` | portable vnode or kernel compatibility fixes |
| Platform | `xnu/patches/mt6765/` or `platform/mt6765/` | interrupt controller, SoC timers, USB controller integration |
| Board | `devices/<device>/` and `xnu/patches/devices/<device>/` | partition map, panel, DTB, RAM ranges, device-specific workarounds |
| Boot tooling | `boot/` and `tools/` | shim builder, ADT generator, image validators |
| Evidence | `docs/devices/<device>/` | verified results, traces and current blockers |

The existing `shim/` implementation remains cactus-specific until independently validated on other devices.

## Patches and reproducibility

- **Never break the legacy filename staging mapping.** The Cactarwin `stage61-cactus-gicr-id-guard` branch has a large ordered patch sequence; build scripts may refer to filenames literally. Audit every patch for device assumptions and dependencies before classifying it.
- Adopt semantic names for new patches: `<sequence>-<scope>-<purpose>.patch`, e.g. `0115-mt6765-gic-redistributor.patch`, `0116-common-mockfs-bounded-read.patch`, or `0117-cactus-display-scanout.patch`. The scope must reflect the **actual** implementation, not the desired portability.
- Maintain the SHA256-checked `xnu/patches/manifest.json` and original→canonical names. Preserve old path → new path mapping and exact content hashes. A patch applying to multiple devices is shared only after testing its assumptions against both configurations.
- Run `python3 tools/stage-patches.py --verify-only`. The workflow stages patches by manifest and preserves their upstream filenames. Never silently skip failed patches or weaken a hash/opcode guard to make a new kernel pass.

## Testing and device safety

- Keep kernel builds and generated images out of Git. Validate kernel provenance, patch order, boot image header, relocation addresses, native instruction pins, RAMDisk and board profile before flashing.
- Verify the device identity and serial **for every flash**. A cactus image must not be flashed to `cph2179` or vice versa. Prefer a device-specific wrapper that refuses mismatches.
- Honor existing hardware authorization and established rollback paths. The owner already maintains cactus boot and recovery backups; do not spend time recreating them unless requested.
- On cactus the established diagnostic path uses Windows PowerShell/WSL, USB CDC traces (Windows COM port varies), and a native framebuffer console. A prehandoff USB trace cannot prove PID 1 ran.
- Record an outcome precisely: `built`, `validated`, `flashed`, `handoff observed`, `native code observed`, `userspace observed`. Do not report `boots iOS` without actual evidence.

## Agent workflow

1. Read the current per-device checkpoint and inspect the relevant sources.
2. Make the smallest *coherent* group of functional changes needed for the requested milestone, preserving unrelated work.
3. Run focused source/patch tests; audit a changed native XNU layout against the actual compiled binary.
4. When a hardware test is authorized and the correct device is detected, use a guarded device-specific flash-and-capture workflow.
5. Update the device checkpoint with exact artifact SHA256, build provenance, observed markers and the next blocker. Keep the public README concise.
6. Do not commit, push or publish unless authorized for that repository and change set. Avoid attributing speculative progress to devices without logs.

## Historical baseline

- Prior source: `austndoesui/Cactarwin`, branch `stage61-cactus-gicr-id-guard`, includes cactus Stage 79 patch `0114-cactus-mockfs-vnode-read-stage79.patch`.
- Current proven cactus boundary: native Stage 79 XNU handoff; PID 1 userspace execution remains unconfirmed.
- Calamansi branches `main`, `generic`, `Cactus`, `cph2179` currently share the initial commit. Branch ownership and CI rules should be established during migration.
