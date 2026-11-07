# Stage81 PID1 VFS boundary / visible event history

The Stage80 physical device reached native XNU and `ST79 mockfs devread finished`, but the higher-level PID1 executable header-read result was not visible. On inspection, the framebuffer routine advanced the original checkpoint string pointer while drawing STATUS, then appended the resulting empty string to the recent-event ring. This is fixed by saving the original string before drawing STATUS.

To narrow the remaining *actual* kernel boundary with one coherent build, the same minimal patch emits `ST81 PID1 VNOP_READ returned` immediately after the VFS read dispatch and `ST81 PID1 vn_rdwr returning` at the read wrapper return. These checkpoints are restricted to process 1, and leave normal VFS and Mach-O loading semantics untouched. Existing ST78 header result and ST80 minimal Mach-O guard remain unchanged.

The supplied minimal init binary is 16,635 bytes, starts with `MH_MAGIC_64=0xfeedfacf`, CPU type ARM64 (`0x0100000c`), and Mach-O file type `MH_EXECUTE=2`. The first XNU header read is a full PAGE_SIZE read; failing after a successful mockfs read is not proof the binary is invalid.

The apparent ~100-second interval between CPU initialization and mockfs completion is user-observed. There is no native timestamped trace for that interval; `ST56` is an earlier milestone, not evidence the CPUs remain busy initializing for 100 seconds. Do not remove SMP/VM/root initialization to skip this period without a demonstrated blocker.
