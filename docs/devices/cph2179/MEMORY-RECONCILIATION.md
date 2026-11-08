# CPH2179 memory map reconciliation

Status: working evidence note; do not use as an XNU allocator map yet.

## Evidence used

- `device/oppo_lfdt.dts`: decompiled FDT captured from `/sys/firmware/fdt` on
  the OPPO A15s Android boot. This is the live FDT Linux received.
- `device/iomem.txt`: captured Linux `/proc/iomem` resource map. Treat it as
  same-boot evidence only if its capture was from the same Android boot as the
  live FDT.
- `device/base-dtb.dts` and `device/oppo6765_1.dts`: boot-image base tree and
  selected DTBO candidate. Applying entry 1 succeeded. The live tree contains
  bootloader-populated data, so it is the primary source for this comparison.

Raw device captures remain outside this repository. Keep them there: the
full-tree diff contains serial, vbmeta, PARTUUID, and other device metadata.

## DRAM span and Linux resource map

The live `/memory/reg` is `<0x00 0x40000000 0x01 0x00>` with two address and
two size cells. This declares the span `[0x40000000, 0x140000000)` (4 GiB).
The base DTB instead declared `[0x40000000, 0x60000000)` (512 MiB); the
bootloader-expanded live value is the relevant one for the Android boot.

The complete `device/iomem.txt` does **not** stop at `0xbfffffff`. Its
`System RAM` resources extend through `0x13fffefff`, consistent with the
live FDT's upper limit apart from the final 4 KiB reservation at
`0x13ffff000-0x13fffffff`. The `System RAM` resources are fragmented:

| Inclusive range | `/proc/iomem` label |
| --- | --- |
| `0x40000000-0x47c7ffff` | System RAM |
| `0x47dd0000-0x77feffff` | System RAM |
| `0x79600000-0x7b86ffff` | System RAM |
| `0x7ffc0000-0x8effffff` | System RAM |
| `0x8f300000-0x9faeffff` | System RAM |
| `0x9ff00000-0xbdffffff` | System RAM |
| `0xbe400000-0xbeffffff` | System RAM |
| `0xbf300000-0xbff2ffff` | System RAM |
| `0xbffb0000-0xbffbefff` | System RAM |
| `0xc0000000-0x13fffefff` | System RAM |

`0xbf000000-0xbf2fffff` is separately labeled `AXI-BUS` in the captured
resource map, although it lies inside the live FDT's declared span. It must
not be treated as allocatable DRAM based on the `/memory` node alone.

The captured `device/meminfo.txt` reports `MemTotal: 3907256 kB`,
`CmaTotal: 274432 kB` (268 MiB), and `CmaFree: 65088 kB`. These are runtime
totals, not physical addresses. In particular, `CmaTotal` cannot identify the
base of a CMA area or be equated with the much larger `zone-movable-cma-memory`
request in the FDT.

### Follow-up runtime capture (2026-11-08)

The successful ADB capture at
`cph2179-runtime-20261108-132219/` identifies the Android device as CPH2179
and records a boot ID. The matching boot ID in the earlier successful captures
shows these files came from the same Android boot. The live FDT is a valid
181143-byte FDT v17; the first collector revision mistakenly filed it as a
`.stderr` file because a broad text search matched the binary string `not
found`. It has been restored to `live-fdt.dtb` in the capture directory.

Cross-checks against the earlier captures pass: the current `/proc/iomem` is
byte-identical to `device/iomem.txt`; the complete `memory/mblock_info`
property is identical to the earlier live FDT; and `/memory/reg`, the fixed
framebuffer range, and ZMC requested size agree. This confirms the existing
FDT and `/proc/iomem` map describe the same memory layout for the captured
Android boot, rather than relying on an assumption about capture timing.
The map still supports the candidate SSPM, SCP, and connectivity placements
listed below, but it does not prove which allocator owns each hole. The Wi-Fi
candidate interval remains inside `System RAM`, and the CMA address cannot be
recovered from its total size.

The readable `/proc/meminfo` reports `MemTotal: 3907256 kB` and
`CmaTotal: 274432 kB`; `CmaFree` is 42188 kB. `/proc/memblock_reserved` does
not exist on this build. The collected dmesg is a late ring-buffer snapshot
whose first visible timestamp is about 10 hours after boot; it contains no
ZMC, reserved-memory, SSPM/SCP, or connectivity allocator messages. It cannot
confirm early-boot allocation addresses. The 48-byte pmsg capture has no
`OPPO6765/SHIM`, XNU, or launchd marker, so none of the boot milestones
advances. The collector was corrected to recognize text errors without
misclassifying arbitrary binary FDT strings and to avoid dumping generic Wi-Fi
logs that contain unrelated network identifiers.

## Bootloader `mblock_info` decoded from live FDT

The live FDT's `memory/mblock_info` property decodes against the available
MT6765 kernel ABI (`../device/A15/kernel-4.9/arch/arm64/include/uapi/asm/setup.h`):
magic `0x99999999`, version 2, 15 `mblock` entries, and 25
`mblock_reserved` entries. Numeric struct fields are byte-swapped relative to
dtc's displayed 32-bit cells; decoding them with the little-endian arm64
struct layout yields the ranges below. Names are the raw struct's 128-byte
strings. This is direct bootloader-provided evidence in the captured live
FDT, though the A15 source header remains a reference ABI for CPH2179.
The table can be regenerated from the decompiled capture with
`python tools/decode_mblock_info.py ../device/oppo_lfdt.dts` from the repo
root.

`mblock` ranges are half-open `[start, start + size)`:

| # | Start | Size | Rank |
| ---: | ---: | ---: | ---: |
| 0 | `0x40000000` | `0x00080000` | 0 |
| 1 | `0x47900000` | `0x00380000` | 0 |
| 2 | `0x47d80000` | `0x00000000` | 0 |
| 3 | `0x47fd0000` | `0x00030000` | 0 |
| 4 | `0x48600000` | `0x00500000` | 0 |
| 5 | `0x50b00000` | `0x01000000` | 0 |
| 6 | `0x55b00000` | `0x1c500000` | 0 |
| 7 | `0x72170000` | `0x05e80000` | 0 |
| 8 | `0x79600000` | `0x01270000` | 0 |
| 9 | `0x80000000` | `0x1fc00000` | 0 |
| 10 | `0x9ff00000` | `0x000f0000` | 0 |
| 11 | `0xa0000000` | `0x0e000000` | 0 |
| 12 | `0xbe000000` | `0x01f30000` | 0 |
| 13 | `0xbffb0000` | `0x0000f000` | 0 |
| 14 | `0xc0000000` | `0x7ffff000` | 1 |

Entry 2 has zero size and is not a usable interval. These are bootloader DRAM
blocks, not a complete Linux free-page map: some ranges are later represented
as reserved resources. `rank` is the DRAM rank field from the ABI.

The named reservations are half-open. The vendor struct documents `mapping`
only as “mapping or unmap”; preserve it as raw metadata until its exact
semantics are confirmed. `map=1` below does not mean the range is allocatable.

| Name | Range | Size | map |
| --- | --- | ---: | ---: |
| `dramc-rk0` | `0xbffff000-0xc0000000` | 4 KiB | 0 |
| `dramc-rk1` | `0x13ffff000-0x140000000` | 4 KiB | 0 |
| `log_store` | `0x7ffc0000-0x80000000` | 256 KiB | 1 |
| `atf-reserved` | `0x47d80000-0x47dd0000` | 320 KiB | 0 |
| `atf-log-reserved` | `0xbffbf000-0xbffff000` | 256 KiB | 0 |
| `SSPM-reserved` | `0x7ff00000-0x7ffc0000` | 768 KiB | 0 |
| `tee-reserved` | `0x7cd00000-0x7ff00000` | 50 MiB | 0 |
| `pl-bootarg` | `0x47dd0000-0x47fd0000` | 2 MiB | 1 |
| `ram_console` | `0x47c80000-0x47c90000` | 64 KiB | 0 |
| `pstore` | `0x47c90000-0x47d70000` | 896 KiB | 0 |
| `minirdump` | `0x47d70000-0x47d80000` | 64 KiB | 0 |
| `lk_addr_mb` | `0x48000000-0x48600000` | 6 MiB | 0 |
| `scratch_addr_mb` | `0x48b00000-0x50b00000` | 128 MiB | 0 |
| `framebuffer` | `0x7b870000-0x7cd00000` | 20.5625 MiB | 0 |
| `logo_db_addr_pa` | `0x7a870000-0x7b870000` | 16 MiB | 0 |
| `atf-ramdump-memory` | `0xbff30000-0xbffb0000` | 512 KiB | 0 |
| `dtb_kernel_addr_mb` | `0x47880000-0x47900000` | 512 KiB | 1 |
| `kernel_addr_mb` | `0x40080000-0x47880000` | 120 MiB | 0 |
| `ramdisk_addr_mb` | `0x51b00000-0x55b00000` | 64 MiB | 0 |
| `SPM-reserved` | `0x77ff0000-0x78000000` | 64 KiB | 0 |
| `SCP-reserved` | `0x9fc00000-0x9ff00000` | 3 MiB | 0 |
| `ccci_tag_mem` | `0x9fff0000-0xa0000000` | 64 KiB | 1 |
| `ccci` | `0xae000000-0xbe000000` | 256 MiB | 1 |
| `md_smem_ncache` | `0x72000000-0x72170000` | 1.4375 MiB | 1 |
| `ccci` | `0x78000000-0x79600000` | 22 MiB | 0 |

This independently confirms the fixed `/reserved-memory` addresses and adds
boot-time buffers relevant to load-address collision checks: LK, scratch,
logo, kernel, ramdisk, DTB, and PL boot arguments. Their release or reuse at
shim handoff is not established by this FDT. Keep half-open arithmetic when
checking adjacency and overlaps.

The captured `/proc/iomem` labels `Kernel code` at
`0x40080000-0x4149ffff` and `Kernel data` at `0x41940000-0x422bbfff`; both
lie inside the bootloader's `kernel_addr_mb` reservation
`[0x40080000,0x47880000)`. This is an additional same-map consistency check
for the decoded named reservation (inclusive Linux resource ends converted
to half-open intervals here).

## Shim/XNU handoff implications

The current `BOARD_OPPO6765` profile in `shim/board.h` still uses the Cactus
framebuffer (`FB_BASE=0x5e605000`, 720x1440), while the captured CPH2179 live
FDT reserves its framebuffer at `[0x7b870000,0x7cd00000)` (720x1600 panel).
Thus the board macro/build label alone does not establish that the image has
CPH2179 display settings. The pmsg `ENTRY` record is written before the shim
initializes its console, so that breadcrumb can still evidence shim entry;
later console/framebuffer output from this profile is not a reliable CPH2179
display test and could write outside the panel framebuffer.

The current Stage27 packer still defines `TEST_RAM = (0x80000000,
0x1e000000)` for its Cactus fixture. That gives `[0x80000000,0x9e000000)`,
which overlaps the source-predicted Android SCP-share interval
`[0x8f000000,0x8f300000)`. This is a warning against carrying the Cactus test
layout over to CPH2179; it is not evidence that a CPH2179 payload currently
uses that range.

The shim's `fdt_region_free()` check sees the live `/memory` range, FDT
memreserve map, and fixed `/reserved-memory` children with `reg`. It does not
resolve size-only dynamic nodes such as the SSPM/SCP/connectivity requests.
On a direct LK-to-shim boot, Linux has not yet performed those allocations,
so Android `/proc/iomem` holes are not necessarily already removed from the
live FDT or RAM. If XNU will use the corresponding firmware/shared-memory
services, its ADT memory map must keep those regions reserved; checking only
fixed FDT `reg` entries cannot establish that. The actual CPH2179 payload ADT
and its `dram-base`/`dram-size` are not present in the current workspace, so
no CPH2179 XNU RAM window is approved by this reconciliation yet.

## Fixed `/reserved-memory` entries

`reg` encodes start and size; the end below is inclusive. “Gap” means the range
is absent from the `System RAM` entries in the captured `/proc/iomem`. A range
inside a `System RAM` resource is still reserved by its FDT owner and is not
considered free merely because the resource parent says `System RAM`.

| Node | Inclusive range | Size | Relation to `/proc/iomem` |
| --- | --- | ---: | --- |
| `mblock-18-ccci` | `0x78000000-0x795fffff` | 22 MiB | Exact RAM gap |
| `mblock-17-md_smem_ncache` | `0x72000000-0x7216ffff` | 1.4375 MiB | Inside System RAM resource |
| `mblock-16-ccci` | `0xae000000-0xbdffffff` | 256 MiB | Inside System RAM resource |
| `mblock-15-ccci_tag_mem` | `0x9fff0000-0x9fffffff` | 64 KiB | Inside System RAM resource |
| `mblock-14-SCP-reserved` | `0x9fc00000-0x9fefffff` | 3 MiB | Exact RAM gap |
| `mblock-13-SPM-reserved` | `0x77ff0000-0x77ffffff` | 64 KiB | Exact RAM gap |
| `mblock-12-atf-ramdump-memory` | `0xbff30000-0xbffaffff` | 512 KiB | Exact RAM gap |
| `mblock-11-framebuffer` | `0x7b870000-0x7ccfffff` | 20.5625 MiB | Exact RAM gap |
| `mblock-10-minirdump` | `0x47d70000-0x47d7ffff` | 64 KiB | Exact RAM gap |
| `mblock-9-pstore` | `0x47c90000-0x47d6ffff` | 896 KiB | Named `persistent_ram` |
| `mblock-8-ram_console` | `0x47c80000-0x47c8ffff` | 64 KiB | Exact RAM gap |
| `mblock-7-tee-reserved` | `0x7cd00000-0x7fefffff` | 50 MiB | Exact RAM gap |
| `mblock-6-SSPM-reserved` | `0x7ff00000-0x7ffbffff` | 768 KiB | Exact RAM gap |
| `mblock-5-atf-log-reserved` | `0xbffbf000-0xbfffefff` | 256 KiB | Exact RAM gap |
| `mblock-4-atf-reserved` | `0x47d80000-0x47dcffff` | 320 KiB | Exact RAM gap |
| `mblock-3-log_store` | `0x7ffc0000-0x7fffffff` | 256 KiB | Inside System RAM resource |
| `mblock-2-dramc-rk1` | `0x13ffff000-0x13fffffff` | 4 KiB | Exact top-of-span gap |
| `mblock-1-dramc-rk0` | `0xbffff000-0xbfffffff` | 4 KiB | Exact RAM gap |

The matching gaps provide strong cross-checks for the fixed ranges. Entries
inside a System RAM resource, especially the 256 MiB CCCI region, need their
MediaTek consumer/reservation behavior confirmed before defining usable memory.

## Dynamic reservations and unresolved ownership

These nodes specify requested size, alignment, and allowed range, but do not
carry a fixed `reg` address in the live FDT. Their possible placements below
are source-based inferences, not confirmed addresses.

| Node | Requested size | Alignment | Allowed range (half-open) |
| --- | ---: | ---: | --- |
| `zone-movable-cma-memory` | `0x7fc00000` | `0x10000000` | `[0xc0000000, 0x240000000)` |
| `reserve-memory-sspm_share` | `0x110000` | `0x10000` | `[0x40000000, 0xa0000000)` |
| `reserve-memory-scp_share` | `0x300000` | `0x1000000` | `[0x40000000, 0x90000000)` |
| `consys-reserve-memory` | `0x400000` | `0x1000000` | `[0x40000000, 0xc0000000)` |
| `wifi-reserve-memory` | `0x300000` | `0x1000000` | `[0x40000000, 0xc0000000)` |

### Source-based placement cross-check (inference, not a runtime log)

The available 4.9 kernel source makes a placement prediction: `mm/memblock.c`
defaults to top-down search (`.bottom_up = false`); its finder walks free
ranges from high to low and rounds candidates down to alignment.
`drivers/of/of_reserved_mem.c` allocates size-only nodes in flat-DT order and
calls `memblock_remove()` for `no-map` allocations. The latest live FDT and
`/proc/iomem` were captured with matching boot IDs, so three predicted hole
sizes and alignments line up in same-boot evidence:

| Node | Predicted interval | Cross-check | Assessment |
| --- | --- | --- | --- |
| `reserve-memory-sspm_share` | `0x9faf0000-0x9fc00000` | Exact `0x110000` hole below fixed SCP reservation; 64 KiB aligned | Strong inference |
| `reserve-memory-scp_share` | `0x8f000000-0x8f300000` | Exact 3 MiB hole; 16 MiB aligned at top of its `< 0x90000000` range | Strong inference |
| `consys-reserve-memory` | `0xbe000000-0xbe400000` | Exact 4 MiB hole; 16 MiB aligned | Strong inference |
| `wifi-reserve-memory` | Expected next candidate `0xad000000-0xad300000` | This interval remains inside the captured `System RAM` resource, rather than appearing as a `no-map` hole | Conflicting evidence: likely allocation failed or node/config differs |
| `zone-movable-cma-memory` | Candidate `0xc0000000-0x13fc00000` | Fits the 4 MiB aligned remainder at the top of its 2 GiB DRAM window; CMA remains System RAM | Plausible, not address-confirmed |

The first three placements have stronger support than size matching alone,
but remain inferred: the A15 source/config is not proven identical to the
running CPH2179 kernel, and the same-boot dmesg snapshot contains no early
allocator messages. Do not count the Wi-Fi region as reserved until runtime
evidence resolves the discrepancy.
The live Wi-Fi node has no `status` property (enabled by default), and the
available kernel registers a `RESERVEDMEM_OF_DECLARE` callback that logs its
base/size when initialization succeeds. Thus the static DTS does not explain
the missing hole; a matching boot log should distinguish allocation failure
from kernel/source or capture mismatch.

`zmc-default` is disabled in the live FDT. `memory/mblock_info` has been
decoded above against the available arm64 ABI; `chosen/atag,mem` remains
vendor-specific and undecoded. The FDT reservation map has no `/memreserve/`
entries in the current decompile.

### Where to get the dynamic addresses

The matching Android kernel's boot log is the best next evidence. The
available reference source is `../device/A15/kernel-4.9` (the OPPO A15 MT6765
kernel); it is a useful guide, but is not proof that CPH2179 runs the exact
same kernel build/configuration.

- `drivers/misc/mediatek/zone_movable_cma/single_cma.c` logs the ZMC node's
  base/size and each registered CMA area's name, size, alignment, and chosen
  interval during `zmc_memory_init()`. This should explain what portion of
  the large FDT request became CMA. `MemTotal`/`CmaTotal` alone cannot recover
  those physical addresses.
- `drivers/misc/mediatek/connectivity/common/connectivity_build_in_adapter.c`
  consumes `consys-reserve-memory` and `wifi-reserve-memory`; its callbacks
  log each final base and size.
- `drivers/misc/mediatek/sspm/sspm_reservedmem.c` and
  `drivers/misc/mediatek/scp/v01/scp_helper.c` consume the SSPM/SCP shared
  regions. Some address messages are `pr_debug`, so they may be absent from a
  normal `dmesg` capture.
- `drivers/misc/mediatek/mem/mtk_memcfg_reserve_info.c` logs entries with the
  `reserved_mem:` prefix on its diagnostic paths; this is useful if enabled,
  but it is not guaranteed to print a complete list in every build.
- If the running kernel was built with `CONFIG_MTK_ENG_BUILD`,
  `drivers/misc/mediatek/mem/mtk_memcfg.c` creates `/proc/memblock_reserved`.
  This reports Linux memblock reservations and, where recorded, the kernel
  call-site backtraces that reserved them. Capturing it can identify ranges
  missing from `/proc/iomem` labels and help distinguish bootloader
  reservations from kernel allocations.

The available `oppo6765_defconfig` enables `CONFIG_MTK_MET_MEM_ALLOC=y`, which
is consistent with the live FDT's 0x110000 SSPM request. The config does not
show the other queried `CONFIG_MTK_*` options explicitly, so their effective
values and whether this config matches the phone's running kernel remain
unverified.

If the phone can boot Android, capture the full kernel log as early as possible
after boot and, if present,
`/proc/memblock_reserved` before attempting the shim again. For example:
`adb shell su -c 'dmesg' > cph2179-dmesg.txt` and
`adb shell su -c 'cat /proc/memblock_reserved' > cph2179-memblock-reserved.txt`
(use `adb shell` without `su -c` if root is not needed). Search the log for
`zmc`, `reserved_mem`, `consys`, `wifi-reserve`, `sspm`, and `scp`; preserve the
surrounding lines and physical addresses. Keep captures private if they
contain serials or other identifiers. If ADB is unavailable, save the
device's existing kernel log or capture UART output. The host-side ADB capture
is now present, but its dmesg ring began long after early boot and the build
does not expose `/proc/memblock_reserved`; allocator ownership and several
dynamic addresses remain unresolved. The agent workspace itself still has no
USB passthrough, so new live reads must be collected on the host and placed in
the shared workspace.

## What is and is not established

- Established for the captured Android boot: the live FDT DRAM span, the fixed
  reserved-memory `reg` intervals, and the Linux `System RAM`/resource ranges
  listed above.
- Not established: runtime-confirmed addresses for the dynamic requests (the
  source-based candidate placements above remain inferences); how every
  vendor reservation inside `System RAM` affects Linux allocation; whether
  the older captures without boot IDs came from this exact boot; and a safe
  XNU allocator range.
- The captured `CmaTotal` is smaller than the FDT's 0x7fc00000
  `zone-movable-cma-memory` request. Their relationship is unknown; do not
  assume they describe the same pool.
- Do not derive “free RAM” by subtracting only named `/reserved-memory`
  entries from the 4 GiB span. Reconcile the Android kernel's actual memory
  ownership and the exact shim/XNU payload placement first.

## Boot evidence milestones

| Milestone | Status | Required evidence |
| --- | --- | --- |
| Shim entered | Not confirmed; current Android pmsg has no shim marker | CPH2179 boot-image provenance plus `OPPO6765/SHIM ENTRY` pmsg or UART marker |
| XNU entered | Not confirmed; no XNU-side marker captured | XNU-emitted marker after its first instruction; shim handoff markers do not count |
| iOS userland reached | Not confirmed; no launchd evidence captured | Evidence that launchd is PID 1 and executed, plus a working userland signal |

The shim has an optional persistent pmsg trace (`BOARD=oppo6765 TRACE_PMSG=1`
with `EARLY_PSTORE=0`). In that build, `dbg_init()` writes `ENTRY` to the
pmsg ring in the reserved pstore area; later breadcrumbs include `loader
enter`, `loader payload`, `xnu jump`, and `xnu handoff`. Current OPPO-targeted
builds label records `OPPO6765/SHIM`; older Cactus captures use
`CACTUS/SHIM`. Preserve the image/build provenance with any retrieved
`/sys/fs/pstore/pmsg-ramoops-0` capture. Pmsg is RAM-backed and may be lost
after power-off or memory reuse.

`xnu handoff` is logged before `xnu_enter_el1`; `xnu el1 reached` is also a
shim checkpoint immediately before the branch to XNU. Neither proves XNU ran
its first instruction. Require an XNU-side marker to advance that row.
A successful build, bootloader logo, or reboot is not evidence of any
milestone. Update the table only when the corresponding device log or other
direct CPH2179 evidence is available.

`shim/TRACE-STAGE18.md` and `docs/devices/cactus/STAGE63` through the later
Cactus stage notes describe Redmi 6A/Cactus work. They are useful references,
but do not advance CPH2179 milestones, even where they show later XNU or PID 1
progress on that different device.

The milestones are sequential in the boot path: first a CPH2179 shim entry
marker, then an XNU entry marker, then launchd/PID 1 plus a working iOS
userland. I can inspect each log you provide and update this table, but I
cannot observe a future phone boot from this workspace by itself.
