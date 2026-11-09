# Stage81 PID1 VFS boundary / visible event history

The Stage80 physical device reached native XNU and `ST79 mockfs devread finished`, but the higher-level PID1 executable header-read result was not visible. On inspection, the framebuffer routine advanced the original checkpoint string pointer while drawing STATUS, then appended the resulting empty string to the recent-event ring. This is fixed by saving the original string before drawing STATUS.

To narrow the remaining *actual* kernel boundary with one coherent build, the same minimal patch emits `ST81 PID1 VNOP_READ returned` immediately after the VFS read dispatch and `ST81 PID1 vn_rdwr returning` at the read wrapper return. These checkpoints are restricted to process 1, and leave normal VFS and Mach-O loading semantics untouched. Existing ST78 header result and ST80 minimal Mach-O guard remain unchanged.

The supplied minimal init binary is 16,635 bytes, starts with `MH_MAGIC_64=0xfeedfacf`, CPU type ARM64 (`0x0100000c`), and Mach-O file type `MH_EXECUTE=2`. The first XNU header read is a full PAGE_SIZE read; failing after a successful mockfs read is not proof the binary is invalid.

The apparent ~100-second interval between CPU initialization and mockfs completion is user-observed. There is no native timestamped trace for that interval; `ST56` is an earlier milestone, not evidence the CPUs remain busy initializing for 100 seconds. Do not remove SMP/VM/root initialization to skip this period without a demonstrated blocker.

## 7 November 2026 build and first hardware replay

- Stage81 XNU patch integrated in Calamansi main commit `2cfb894` and macOS GitHub Actions run `42385859444` **SUCCESS**. Kernel SHA256 `c38d4ebda19c66931bb20167393ba62f377bb18df693fe26f416f67c136bb4cf`, 17,139,024 bytes.
- Calamansi Stage81 relocation payload SHA256 `b015cea97bbf056142477cd645faaaccac5b9b80e6f7830fddeb2097ee1cf781`, with exact 41 opcode/layout checks passing. Native entry PA `0x8142c488`, XNU C entry PA `0x81abf53c`, boot_args PA `0x824c4000`, RAMDisk PA `0x824b8000`.
- Final boot image: `shim/out/cactus/cactus-trace-stage-81-boot.img`, 45,522,944 bytes; SHA256 `56518963d389bec759124e2045668cc05543a17c9b7ceb181a55d232fd6fbd68`. Boot v2 header and local image checksum validated. Verified fastboot product `cactus`, serial supplied explicitly to `shim/run-stage49.ps1`; send/write/reboot returned OKAY.
- Capture: `usb-captures/stage-cactus-20261107-210953-124/session-001-211003-163.bin`: **80 valid frames**, 0 corrupt, 10 missing sequence numbers, no duplicate/regression. Event `0x2800` reports Stage81 kernel identity `0xc38d4ebda19c6693`, `0x3500` confirms native XNU entry `0x8142c488` with boot_args `0x824c4000`.
- COM25's endpoint reports only pre-XNU handoff; it cannot establish whether the new native framebuffer event history, `ST81 PID1 VNOP_READ returned`, or `ST81 PID1 vn_rdwr returning` appeared. Await physical framebuffer evidence; PID 1 instruction execution remains unconfirmed.
