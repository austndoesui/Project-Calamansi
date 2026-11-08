# CPH2179

Independent target, not yet hardware-verified. No XNU execution, framebuffer,
memory-layout handoff, or paging claims are made. The Cactus flash scripts are
not suitable for this device.

## Shim entry probe

The first OPPO hardware probe is an entry-only shim build. It writes an
`OPPO6765/SHIM shim entry before EL gate` breadcrumb (including CurrentEL,
incoming DTB pointer, and MPIDR) to the existing ramoops pmsg area before the
exception-level gate, then waits in `WFE`. It does not initialize the Cactus
framebuffer/debug console, arm the watchdog, parse memory for XNU, or transfer
control to XNU.

Reproduce it from `shim/`:

```sh
OPPO_ENTRY_ONLY=1 BOARD=oppo6765 TRACE_PMSG=1 EARLY_PSTORE=0 ./build.sh
```

Artifact: `shim/out/oppo6765/shim-entry-only-boot.img`  
SHA256: `7ae49a57170801d076a488c38fc07e78b1d3bde72f88f3ddd469296891181482`  
Build result: image header inspected; 8,587,264 bytes; fits the recorded
32 MiB `boot` partition. It embeds a copy of the captured live FDT with the
`/chosen/bootargs` property removed; the boot image header command line is
empty. It also contains the captured 8 MiB DTBO image.
The user reports flashing an entry-only shim and recovering Android, but has
not confirmed the flashed file's SHA256. The resulting pmsg capture contained
no shim marker, so shim entry remains unconfirmed.

The extracted stock boot image is `../device/boot.img`, SHA256
`210f2383d822b7a88653c39a15da9bde5bfae410fef12e8d5ae0e82f45cbb001`.
Keep it available as the restore image. Before flashing, verify fastboot entry
and the recovery route from a stalled boot on the actual phone. For every
flash, verify the connected device's serial and `fastboot getvar product`
reports `oppo6765`; the earlier saved fastboot inventory reports product
`oppo6765` and `slot-count: 0`, but recheck live.

After a shim-only boot, use the verified hardware route back to fastboot,
restore the saved stock image to `boot`, then boot Android and collect
`/sys/fs/pstore/pmsg-ramoops-0`. The `ENTRY` marker confirms shim entry only;
it does not show XNU execution or iOS userspace.

Latest shared capture (`cph2179-runtime-20261108-145248/`): pstore listed
only `console-ramoops`; `pmsg-ramoops-0` was absent. The 262,132-byte console
dump is partially garbled. Its readable tail shows Android init requesting a
reboot to bootloader (`arch_reset: cmd = bootloader`) and the associated reset
call trace; this is not a kernel panic signature. No `OPPO6765/SHIM` marker is
present, so this capture does not confirm shim entry. The standalone
`console-ramoops` file matches that capture byte-for-byte.

The pmsg self-test later succeeded across a warm reboot: the user found
`CALAMANSI_PMSG_SELFTEST` in `pmsg-ramoops-0`. This confirms Android pmsg
capture is available. The rebuilt probe moves its marker ahead of the shim's
CurrentEL gate, so a later captured `shim entry before EL gate` marker will
confirm `_start` was reached and report the entry level; it still will not
confirm XNU execution.

The first flashed entry-only attempt displayed `[ERROR] CMDLINE overflow`.
This is consistent with LK rejecting an overlong assembled kernel command
line before kernel entry. The captured live FDT carried LK's full runtime
arguments in `/chosen/bootargs`; this rebuild shortens that property and clears
the image header command line. The change is a mitigation to retry, not yet a
device-verified fix.

The later reported flash produced no shim pmsg marker. The exact flashed image
hash and whether `[ERROR] CMDLINE overflow` remained on screen were not
reported. Do not count this as shim entry or as confirmation that the
command-line mitigation worked.

## Bounded CDC heartbeat probe

The separate CDC probe emits the early pmsg entry record, checks the MT6765
MUSB hardware ID, then attempts CDC-ACM and sends `OPPO6765 HB <sequence>` lines
for up to 20 seconds. Pmsg records distinguish `CDC_INIT_FAIL`, `CDC_INIT_OK`,
the first queued heartbeat, and completion. It does not initialize the
framebuffer, arm the Cactus watchdog, parse memory for XNU, or transfer to XNU.

Build with:

```sh
OPPO_CDC_HEARTBEAT=1 BOARD=oppo6765 TRACE_PMSG=1 EARLY_PSTORE=0 ./build.sh
```

Artifact: `shim/out/oppo6765/shim-cdc-heartbeat-boot.img`  
SHA256: `239f2a318be749bd912039502faaf4b449874e15c03a4517805726ea330edad4`  
That version was reported flashed and still showed `[ERROR] CMDLINE overflow`.
It had an empty image-header command line but retained a short FDT
`/chosen/bootargs` property. The current rebuild removes that property
entirely and has SHA256
`9c8ba134368cd9ba35b9dbed13a91e01dd45d2fd4846754c3c82c10d19d90b83`.
The current image is built and header-inspected, not yet flashed. The OPPO
A15 kernel tree confirms the MT6765 controller and PHY windows used by the
probe; CDC initialization and heartbeat reception remain unverified on
CPH2179. Start the host capture before rebooting the phone:

```sh
tools/cph2179-cdc-capture.sh cph2179-cdc-heartbeat.txt 30
```

The helper waits for a `/dev/ttyACM*` or `/dev/ttyUSB*` node and captures its
raw CDC data. A serial device appearing is not itself proof the heartbeat was
received; look for multiple numbered `OPPO6765 HB` lines.

The matching entry-only image was also rebuilt with `/chosen/bootargs`
removed; its hash is listed above. The LK image contains the same
`[ERROR] CMDLINE overflow` message and a 1024-byte command-line buffer pattern
is present in public MTK LK source. Removing the remaining FDT property is a
new mitigation hypothesis, not a verified resolution. Verify the exact image
hash before another flash.

## Stage 15 boot-v2 packaging update

The OPPO build now takes the DT table, ramdisk, and short header command line
from the stock CPH2179 boot-v2 image. It puts only the compressed shim in the
kernel component; it no longer appends the live FDT or supplies the separate
DTBO image as the boot-v2 DTB. This avoids duplicating LK's runtime command
line in the image components. The stock boot image is a required local input;
set `OPPO_STOCK_BOOT=/path/to/stock/boot.img` when building.

Built and header-checked, not flashed:

- Regular Stage 15: `shim/out/oppo6765/shim-stage15-cmdline-fix-boot.img`,
  SHA256 `28965bfc32d05da98d64cfadb2fb4e29c301696488b70aa7964ef8d1a23c97a4`.
- Early Stage 15 level 5: `shim/out/oppo6765/shim-stage15-early5-cmdline-fix-boot.img`,
  SHA256 `8dafb7e49a933fc646d40ff500df9622e8c7bb2e16a9334830c432a10dfc4b7a`.

Both retain the stock boot-v2 fields: 2048-byte page size, kernel address
`0x40080000`, ramdisk address `0x51b00000`, tags/DTB address `0x47880000`,
and header command line `bootopt=64S3,32N2,64N2 buildvariant=user`. The fix is
not confirmed on-device until the exact image hash is flashed and the phone
passes the former LK overflow screen.

## Stage 15 CDC captures and DTR holdoff

The Early Stage 15 capture (`oppo-cdc.bin`, session `0xca15e005`) had valid
frames with no CRC errors, gaps, or duplicates, but started at sequence 3 and
ended after `DBG_AFTER`. It does not show the later watchdog or FDT markers.
The later DTR-debounce capture (`oppo-dtrdebounce.bin`, same session) improved
to 42 valid frames with zero CRC errors, gaps, or duplicates, and includes
sequence 0 `ENTRY` and sequence 1 `USB_INIT` (`connected=1`, EL2). It still
ends after `DBG_AFTER` and three heartbeats; it has no watchdog-before/after,
FDT, reservation, or done markers. The capture does not establish whether the
shim reset, hung, or the host capture stopped early.
The regular Stage 15 capture (`oppo-cdc2.bin`, session `0xca150001`) showed
shim entry, successful FDT parsing, then stopped with `no SWEETXNU payload`;
the image used the stock Android ramdisk, which contains no Calamansi payload.
This confirms shim, USB, and FDT progress, not XNU execution.

Both Stage 15 send paths now wait for DTR to remain asserted for 250 ms before
transmitting queued trace frames, giving the host time to configure its reader.
Early level 5 also reports fixed FDT reservations and the decoder now validates
that level's reservation count.
These rebuilt images passed the boot-v2 header check; they have not yet been
flashed:

- Regular Stage 15:
  `shim/out/oppo6765/shim-stage15-dtr-debounce-boot.img`, SHA256
  `3e4e38b45c9e1c033b5b7692f22524130efd08e31ec1d7a5fdf05c0db012c062`.
- Early Stage 15 level 5:
  `shim/out/oppo6765/shim-stage15-early5-dtr-wdt-boot.img`, SHA256
  `8f2d8110c5fe95c34c6bddc0390fd53ad45b4cd3e1970f25e16d3dca9ef92b0c`.
  This build adds the 30-second early watchdog setup to test whether LK's
  watchdog caused the earlier trace to stop after `DBG_AFTER`.

The next XNU handoff prerequisite is a valid `SWEETXNU` payload and generated
ADT that pass the OPPO memory/layout validator.

### Early Stage 15 level 5 verified

The subsequent `oppo-early-wdt.bin` capture passes the level 5 decoder:
123 valid frames, zero bad frames/unmatched bytes/gaps/duplicates/regressions,
session `0xca15e005`, and the complete event set through `STAGE15_DONE`
(`0x158a`). It includes watchdog setup before/after, successful FDT inspection
(`0x1588`: result 0, size `0x2c397`, one DRAM bank), the `FDT_DONE` record
(`0x1589`: DRAM `0x40000000`–`0x140000000`), and 18 fixed reservation ranges
(`0x158c`). The decoder reports `STAGE15 EARLY PASS`.

This verifies the early shim diagnostic path through FDT/reservation reporting
on the phone. It does not yet validate that those ranges are safe for XNU, nor
does it show an XNU handoff or iOS userspace boot. Preserve the capture and
image hash alongside any later memory-layout reconciliation.

## XNU RAM window is unresolved

The current `SWEETXNU` payload ABI carries one contiguous `phys_base` / `mem_size`
window, plus kernel segments, ADT, and boot arguments inside that window. The
loader validates that whole window against the live FDT and the 16 KiB payload
alignment. The existing Cactus example uses `[0x70000000, 0xc0000000)` (1.25
GiB); that is a Cactus configuration, not an XNU minimum-memory requirement,
and it overlaps OPPO reservations.

The conservative comparison, subtracting the 33 captured Android runtime
memblock reservations as well as FDT and bootloader reservations, leaves a
largest 16 KiB-aligned contiguous interval of `[0xc0000000, 0xffff4000)`
(`0x3fff4000` bytes, just under 1 GiB). It is inside the reported System RAM
bank and bootloader mblock #14, and avoids every reservation in those captures.
This is a **candidate for an XNU diagnostic window**, not an approved final
layout: Android runtime reservations may include Linux-specific allocations,
and no CPH2179 XNU payload has been built and measured against it. The smaller
`[0x55b00000, 0x72000000)` interval is 453 MiB and is also only a candidate.

The current payload format represents one contiguous window, not fragmented
RAM as multiple independently usable extents. Before choosing a production
window, measure the actual kernel segments/ADT/bootargs and decide whether this
device can boot with the candidate extent or the XNU memory-map/loader path
must be extended for discontiguous RAM. Do not copy the Cactus base/size to the
OPPO ADT.
