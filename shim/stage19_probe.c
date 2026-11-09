/*
 * Stage19-A: copy the actual ten XNU segments, Apple ADT and boot_args
 * into the FDT-verified 480 MiB DRAM window. Verify every copy while
 * retaining the Stage18 USB logger and working TWRP return.
 * No EL change, MMU enable, kernel jump or persistent storage writes.
 */
#include <stdint.h>
#include "cactus_trace.h"
#include "cactus_usb.h"
#include "fdt.h"
#include "fdt_ranges.h"
#include "payload_layout.h"
#include "console.h"

#ifndef PAYLOAD_ADDR
#error Stage19 requires the physical pointer to the embedded XNU payload
#endif
#ifndef PAYLOAD_LENGTH
#error Stage19 requires the embedded XNU payload length
#endif

enum {
    S19_ENTRY=0x1900, S19_USB=0x1901, S19_BEAT=0x1902,
    S19_FDT=0x1910, S19_VALID=0x1911, S19_PAYLOAD=0x1912,
    S19_BEFORE_COPY=0x1930,
    S19_SEG_START=0x1940, S19_SEG_DONE=0x1941,
    S19_ADT=0x1950, S19_BOOTARGS=0x1951, S19_COPY_DONE=0x1952,
    S19_DONE=0x19ff, S19_FAULT=0x19ee
};

struct boot_video {
    uint64_t v_baseAddr, v_display, v_rowBytes, v_width, v_height, v_depth;
};
struct boot_args {
    uint16_t Revision, Version;
    uint64_t virtBase, physBase, memSize, topOfKernelData;
    struct boot_video Video;
    uint32_t machineType;
    uint64_t deviceTreeP;
    uint32_t deviceTreeLength;
    char CommandLine[608];
    uint64_t bootFlags, memSizeActual;
};
_Static_assert(__builtin_offsetof(struct boot_args, Video)==40,
               "boot_args Video offset");
_Static_assert(__builtin_offsetof(struct boot_args, CommandLine)==108,
               "boot_args cmdline offset");
_Static_assert(sizeof(struct boot_args)==736, "boot_args ABI");

static uint32_t usb_diag[16];
static uint64_t frequency;
static unsigned online, faulted, heartbeat_count;
static void mark(unsigned event, uint64_t a, uint64_t b, uint64_t c);
#if defined(CACTUS_STAGE88_MSDC_READ) && CACTUS_STAGE88_MSDC_READ
/*
 * Cactus MT6765 MSDC0: bounded READ-ONLY proof of access to an existing GPT.
 * The MT6765 Linux DTS defines controller 0 at PA 0x11230000; the register
 * offsets and interrupt bits are cross-checked with its msdc_reg.h. Probe
 * while the shim still has identity-mapped physical MMIO and USB logging.
 * Never issue a write-to-card MMC command or reset/reclock the controller.
 * A failed probe must not prevent the unchanged XNU handoff.
 */
enum {
    C88_MSDC_PA = 0x11230000u,
    C88_CFG = 0x00u, C88_INTR = 0x0cu, C88_INTEN = 0x10u,
    C88_FIFO = 0x14u, C88_RX = 0x1cu, C88_SDC_CFG = 0x30u,
    C88_CMD = 0x34u, C88_ARG = 0x38u, C88_STS = 0x3cu,
    C88_RESP = 0x40u, C88_BLKNUM = 0x50u,
    C88_CMDRDY = 1u << 8, C88_CMDERR = (1u << 9) | (1u << 10),
    C88_DATAOK = 1u << 12, C88_DATAERR = (1u << 14) | (1u << 15)
};
static uint32_t cactus88_mmio(unsigned offset)
{
    return *(volatile const uint32_t *)(uintptr_t)(C88_MSDC_PA + offset);
}
static void cactus88_write(unsigned offset, uint32_t value)
{
    *(volatile uint32_t *)(uintptr_t)(C88_MSDC_PA + offset) = value;
    __asm__ volatile("dsb sy" ::: "memory");
}
static uint64_t cactus88_time(void)
{
    uint64_t ticks;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(ticks));
    return ticks;
}
static int cactus88_wait_clear(unsigned offset, uint32_t bits)
{
    const uint64_t start = cactus88_time();
    while (cactus88_time() - start < frequency * 2u)
        if (!(cactus88_mmio(offset) & bits)) return 0;
    return -1;
}
static int cactus88_command(unsigned opcode, uint32_t arg, int data,
                             uint32_t *response)
{
    if (cactus88_wait_clear(C88_STS, opcode == 13 ? 2u : 1u)) return 1;
    cactus88_write(C88_INTR, cactus88_mmio(C88_INTR));
    cactus88_write(C88_ARG, arg);
    cactus88_write(C88_CMD, opcode | (1u << 7) |
                   (data ? (1u << 11) | (512u << 16) : 0));
    const uint64_t start = cactus88_time();
    while (cactus88_time() - start < frequency * 2u) {
        uint32_t status = cactus88_mmio(C88_INTR) &
                          (C88_CMDRDY | C88_CMDERR);
        if (!status) continue;
        cactus88_write(C88_INTR, status);
        if (status & C88_CMDERR) return 2;
        *response = cactus88_mmio(C88_RESP);
        return (*response & 0xfdffa080u) ? 3 : 0;
    }
    return 4;
}
static uint32_t cactus88_le32(const uint8_t *b)
{
    return (uint32_t)b[0] | ((uint32_t)b[1] << 8) |
           ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
}
static int cactus88_read_lba(uint32_t sector, uint8_t buf[512],
                              uint32_t *response)
{
    cactus88_write(C88_BLKNUM, 1);
    cactus88_write(C88_FIFO, cactus88_mmio(C88_FIFO) | (1u << 31));
    if (cactus88_wait_clear(C88_FIFO, 1u << 31)) return 5;
    int err = cactus88_command(17u, sector, 1, response);
    if (err) return err + 10;
    const uint64_t start = cactus88_time();
    unsigned at = 0;
    int done = 0;
    while (cactus88_time() - start < frequency * 2u) {
        uint32_t irq = cactus88_mmio(C88_INTR) &
                       (C88_DATAOK | C88_DATAERR);
        if (irq) {
            cactus88_write(C88_INTR, irq);
            if (irq & C88_DATAERR) return 20;
            done = 1;
        }
        unsigned available = cactus88_mmio(C88_FIFO) & 255u;
        while (available >= 4u && at < 512u) {
            uint32_t word = cactus88_mmio(C88_RX);
            buf[at++] = (uint8_t)word;
            buf[at++] = (uint8_t)(word >> 8);
            buf[at++] = (uint8_t)(word >> 16);
            buf[at++] = (uint8_t)(word >> 24);
            available -= 4u;
        }
        if (done && at == 512u) return 0;
    }
    return 21;
}
static uint32_t cactus88_header_crc(const uint8_t *b, unsigned size)
{
    uint32_t crc = ~0u;
    for (unsigned i = 0; i < size; i++) {
        uint8_t value = (i >= 16u && i < 20u) ? 0 : b[i];
        crc ^= value;
        for (unsigned j = 0; j < 8; j++)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}
static void cactus88_probe_emmc(void)
{
    const uint32_t original_cfg = cactus88_mmio(C88_CFG);
    const uint32_t original_inten = cactus88_mmio(C88_INTEN);
    const uint32_t sdc_cfg = cactus88_mmio(C88_SDC_CFG);
    const uint32_t status = cactus88_mmio(C88_STS);
    mark(0x8800u, C88_MSDC_PA,
         ((uint64_t)original_cfg << 32) | sdc_cfg,
         ((uint64_t)original_inten << 32) | status);
    /* CKSTB must be set: do not initialize, power-cycle, or retune eMMC. */
    if (!(original_cfg & (1u << 7))) {
        mark(0x880fu, 1u, original_cfg, status);
        return;
    }
    cactus88_write(C88_INTEN, 0u);
    cactus88_write(C88_CFG, original_cfg | (1u << 3));
    uint32_t r1 = 0;
    const int cmd13 = cactus88_command(13, 1u << 16, 0, &r1);
    mark(0x8801u, cmd13, r1, cactus88_mmio(C88_INTR));
    if (!cmd13 && ((r1 >> 9) & 15u) == 4u) {
        const uint32_t locations[2] = {1u, 0x1c01u};
        for (unsigned i = 0; i < 2u; i++) {
            uint8_t header[512];
            uint32_t read_response = 0;
            int err = cactus88_read_lba(locations[i], header, &read_response);
            mark(0x8802u, locations[i], err, read_response);
            if (err) break;
            const uint32_t magic_lo = cactus88_le32(header);
            const uint32_t magic_hi = cactus88_le32(header + 4u);
            const uint32_t size = cactus88_le32(header + 12u);
            const uint32_t expected_crc = cactus88_le32(header + 16u);
            uint32_t actual_crc = 0;
            if (magic_lo == 0x20494645u && magic_hi == 0x54524150u &&
                size >= 92u && size <= 512u)
                actual_crc = cactus88_header_crc(header, size);
            mark(0x8803u, locations[i],
                 ((uint64_t)magic_hi << 32) | magic_lo,
                 ((uint64_t)expected_crc << 32) | actual_crc);
            if (expected_crc && expected_crc == actual_crc) {
                mark(0x8804u, locations[i], cactus88_le32(header + 80u),
                     cactus88_le32(header + 84u));
                break;
            }
        }
    }
    cactus88_write(C88_INTR, cactus88_mmio(C88_INTR));
    cactus88_write(C88_CFG, original_cfg);
    cactus88_write(C88_INTEN, original_inten);
    mark(0x880eu, original_cfg, original_inten, cactus88_mmio(C88_CFG));
}
#endif
#if defined(CACTUS_STAGE62_GICR_MMIO) && CACTUS_STAGE62_GICR_MMIO
/* Read the MT6765 GIC registers from EL2 with the shim's MMU disabled,
 * before entering XNU's separate ml_io_map() mappings. Stage61 now panics
 * while rejecting all redistributors; this distinguishes a real MMIO frame
 * from a zero-fill, security read-as-zero, or incorrect XNU mapping.
 * Only read architected identity registers. Never modify interrupt state. */
static void stage62_gicr_physical_census(void)
{
    const uintptr_t gicd = 0x0c000000u;
    const uintptr_t gicr = 0x0c100000u;
    uint64_t mpidr;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(mpidr));
    const uint32_t d_pidr2 = *(volatile const uint32_t *)(gicd + 0xffe8u);
    const uint32_t d_typer = *(volatile const uint32_t *)(gicd + 0x4u);
    mark(0x6200u, mpidr, ((uint64_t)d_pidr2 << 32) | d_typer, gicr);
    for (uintptr_t offset = 0; offset < 0x200000u; offset += 0x20000u) {
        const uintptr_t frame = gicr + offset;
        const uint32_t pidr2 = *(volatile const uint32_t *)(frame + 0xffe8u);
        const uint64_t typer = *(volatile const uint64_t *)(frame + 0x8u);
        mark(0x6201u, frame, pidr2, typer);
        /* GICR_TYPER.Last is bit 4 in the low word. */
        if (typer & 0x10u) break;
    }
    __asm__ volatile("dsb sy" ::: "memory");
    mark(0x6202u, 0x01000000u, 0x0b100000u, 0x0c100000u);
}
#endif
#if defined(CACTUS_STAGE20) && CACTUS_STAGE20
static uint64_t loaded_entry_pa, loaded_boot_args_pa;
#endif
#if defined(CACTUS_STAGE20B) && CACTUS_STAGE20B
#if defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
/* Stage53's verified Mach-O layout is 0x3000 earlier than Stage52, while
 * the C arm_init function itself moved +0x2300 relative to Stage51. */
#if defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
#define STAGE52_NATIVE_SHIFT (0ull - 0x1000ull) /* independently checked Stage78 native relocation */
#else
#define STAGE52_NATIVE_SHIFT 0ull
#endif
#define STAGE53_C_SHIFT 0x2300ull
#if defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
#define STAGE54_C_SHIFT 0x150ull
#if defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
/* The audited Stage55 Mach-O advances the native arm_init prologue 0x60. */
#define STAGE55_C_SHIFT 0x60ull
#if defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
#define STAGE56_C_SHIFT 0xb0ull
#if defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
#define STAGE57_C_SHIFT 0x1e0ull /* verified Actions 40167462565 */
#else
#define STAGE57_C_SHIFT 0ull
#endif
#else
#define STAGE56_C_SHIFT 0ull
#define STAGE57_C_SHIFT 0ull
#endif
#else
#define STAGE55_C_SHIFT 0ull
#define STAGE56_C_SHIFT 0ull
#define STAGE57_C_SHIFT 0ull
#endif
#else
#define STAGE54_C_SHIFT 0ull
#define STAGE55_C_SHIFT 0ull
#define STAGE56_C_SHIFT 0ull
#define STAGE57_C_SHIFT 0ull
#endif
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
/* Exact binary relocation of the Stage52 kernel: __TEXT grew by 0x3000
 * and its bootstrap/vector code moved with it. Native C must be re-pinned
 * separately: its branch opcodes changed after adding console marks. */
#define STAGE52_NATIVE_SHIFT 0x3000ull
#define STAGE53_C_SHIFT 0ull
#define STAGE54_C_SHIFT 0ull
#define STAGE55_C_SHIFT 0ull
#define STAGE56_C_SHIFT 0ull
#define STAGE57_C_SHIFT 0ull
#else
#define STAGE52_NATIVE_SHIFT 0ull
#define STAGE53_C_SHIFT 0ull
#define STAGE54_C_SHIFT 0ull
#define STAGE55_C_SHIFT 0ull
#define STAGE56_C_SHIFT 0ull
#define STAGE57_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
#define STAGE58_C_SHIFT 0x330ull /* verified Actions 40172527110 */
#else
#define STAGE58_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
#define STAGE59_C_SHIFT 0xe0ull /* verified Actions 40174697930 */
#else
#define STAGE59_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
#define STAGE60_C_SHIFT 0x120ull /* verified Actions 40177248576 */
#else
#define STAGE60_C_SHIFT 0ull
#endif
/* Stage61 is fail closed until its freshly built Mach-O branch pins land. */
#if defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
#define STAGE61_C_SHIFT 0x10ull /* verified Actions 40225061014 */
#else
#define STAGE61_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
#define STAGE63_C_SHIFT 0x90ull /* audited Stage63 C entry and join */
#else
#define STAGE63_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
#define STAGE65_C_SHIFT 0x220ull /* audited Stage65 new early C layout */
#else
#define STAGE65_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
#define STAGE67_C_SHIFT 0x190ull /* actual Stage67 early-C delta from Stage65 */
#else
#define STAGE67_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
#define STAGE68_C_SHIFT 0x120ull
#else
#define STAGE68_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
#define STAGE69_C_SHIFT 0x200ull
#else
#define STAGE69_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
#define STAGE70_C_SHIFT (0ull - 0x40ull) /* Stage70 reduced native early C by 0x40 bytes */
#else
#define STAGE70_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
#define STAGE71_C_SHIFT (0ull - 0x1a0ull) /* Stage71 native early C delta from Stage70 */
#else
#define STAGE71_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
#define STAGE72_C_SHIFT (0ull - 0x20ull) /* Stage72 early C delta from Stage71 */
#else
#define STAGE72_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
#define STAGE73_C_SHIFT 0x40ull /* Stage73 native early C delta from Stage72 */
#else
#define STAGE73_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
#define STAGE74_C_SHIFT 0x180ull /* Stage74 native early-C delta from Stage73 */
#else
#define STAGE74_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
#define STAGE75_C_SHIFT 0x320ull /* Stage75 early C delta from Stage74 */
#else
#define STAGE75_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
#define STAGE76_C_SHIFT 0x20ull /* Stage76 native C delta from Stage75 */
#else
#define STAGE76_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
#define STAGE77_C_SHIFT 0x120ull /* observed verified Stage77 native C delta */
#else
#define STAGE77_C_SHIFT 0ull
#endif
#if defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
#define STAGE78_C_SHIFT (0ull - 0x49c0ull) /* + -0x1000 from native = total -0x59c0 */
#else
#define STAGE78_C_SHIFT 0ull
#endif
#define STAGE20B_ENTRY  (0x8142d488ull+STAGE52_NATIVE_SHIFT)
#define STAGE20B_ENTRY_TARGET (0x8142f0ecull+STAGE52_NATIVE_SHIFT)
#if defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
/* Fresh run 40099595534 added one 2MiB framebuffer descriptor to the
 * MMU bootstrap and shifted the native early-C entry by 0x20 bytes.
 * Older stage runtime/checkpoint pins remain intact in the else paths. */
#define STAGE51_EARLY_C_OFFSET 0x20ull
#define STAGE51_MMU_OFFSET 0x0cull
#else
#define STAGE51_EARLY_C_OFFSET 0ull
#define STAGE51_MMU_OFFSET 0ull
#endif
#if defined(CACTUS_STAGE20C) && CACTUS_STAGE20C
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
#if defined(CACTUS_STAGE22) && CACTUS_STAGE22
#if defined(CACTUS_STAGE43_NEXT_INIT) && CACTUS_STAGE43_NEXT_INIT
/* Following second lookup and conditional read, before next C call. */
#define STAGE20B_TARGET 0x81ac0c64ull
#define STAGE20B_ORIG   0x97dfab47u /* bl 0xfffffff0072ab980 */
#define STAGE20B_BRK    0xd421c860u /* brk #0xe43 */
#define STAGE20B_IMM    0xe43u
#define STAGE20B_ARM_EVENT 0x2204u
#define STAGE20B_TRAP_EVENT 0x2206u
#define STAGE20B_RESTORE_EVENT 0x220bu
#define STAGE22_TARGET_VA 0xfffffff007ac0c64ull
#elif defined(CACTUS_STAGE44_NEXT_RETURN) && CACTUS_STAGE44_NEXT_RETURN
/* Check that the next initialization call completed and returned. */
#define STAGE20B_TARGET 0x81ac0c68ull
#define STAGE20B_ORIG   0x90ffb5c8u /* adrp x8,... */
#define STAGE20B_BRK    0xd421c880u /* brk #0xe44 */
#define STAGE20B_IMM    0xe44u
#define STAGE20B_ARM_EVENT 0x2204u
#define STAGE20B_TRAP_EVENT 0x2206u
#define STAGE20B_RESTORE_EVENT 0x220bu
#define STAGE22_TARGET_VA 0xfffffff007ac0c68ull
#elif defined(CACTUS_STAGE41_CALLEE_ENTRY) && CACTUS_STAGE41_CALLEE_ENTRY
/* First instruction of the called early-C boot-argument lookup routine. */
#define STAGE20B_TARGET 0x81a5dcb0ull
#define STAGE20B_ORIG   0xd10303ffu /* sub sp,sp,#0xc0 */
#define STAGE20B_BRK    0xd421c820u /* brk #0xe41 */
#define STAGE20B_IMM    0xe41u
#define STAGE20B_ARM_EVENT 0x2204u
#define STAGE20B_TRAP_EVENT 0x2206u
#define STAGE20B_RESTORE_EVENT 0x220bu
#define STAGE22_TARGET_VA 0xfffffff007a5dcb0ull
#elif defined(CACTUS_STAGE42_AFTER_CALLEE) && CACTUS_STAGE42_AFTER_CALLEE
/* Instruction after the BL returns to XNU early-C initialization. */
#define STAGE20B_TARGET 0x81ac0c24ull
#define STAGE20B_ORIG   0x7100041fu /* cmp w0,#1 */
#define STAGE20B_BRK    0xd421c840u /* brk #0xe42 */
#define STAGE20B_IMM    0xe42u
#define STAGE20B_ARM_EVENT 0x2204u
#define STAGE20B_TRAP_EVENT 0x2206u
#define STAGE20B_RESTORE_EVENT 0x220bu
#define STAGE22_TARGET_VA 0xfffffff007ac0c24ull
#elif defined(CACTUS_STAGE40_LATE_C) && CACTUS_STAGE40_LATE_C
/* Stage40: first boot-argument lookup after the proven Stage36 C join.
 * Patch the exact rebuilt-XNU BL only while the ELF is still physical.
 * If this BRK is hit, XNU reached an instruction beyond Stage36. */
#define STAGE20B_TARGET 0x81ac0c20ull
#define STAGE20B_ORIG   0x97fe7424u /* bl early boot-arg lookup */
#define STAGE20B_BRK    0xd421c800u /* brk #0xe40 */
#define STAGE20B_IMM    0xe40u
#define STAGE20B_ARM_EVENT 0x2204u
#define STAGE20B_TRAP_EVENT 0x2206u
#define STAGE20B_RESTORE_EVENT 0x220bu
#define STAGE22_TARGET_VA 0xfffffff007ac0c20ull
#else
#if defined(CACTUS_STAGE96_NATIVE) && CACTUS_STAGE96_NATIVE
#include "out/cactus/stage96-pins.h"
#define STAGE20B_TARGET 0x81ac042cull
#define STAGE20B_ORIG   CACTUS96_WORD_81AC042C
#elif defined(CACTUS_STAGE95_NATIVE) && CACTUS_STAGE95_NATIVE
#define STAGE20B_TARGET 0x81ac042cull
#define STAGE20B_ORIG   0x913a5400u
#elif defined(CACTUS_STAGE91_NATIVE) && CACTUS_STAGE91_NATIVE
#define STAGE20B_TARGET 0x81ac042cull
#define STAGE20B_ORIG   0x913e0d29u
#elif defined(CACTUS_STAGE90_NATIVE) && CACTUS_STAGE90_NATIVE
#define STAGE20B_TARGET 0x81ac042cull
#define STAGE20B_ORIG   0x9107dc00u
#elif defined(CACTUS_STAGE89_NATIVE) && CACTUS_STAGE89_NATIVE
#define STAGE20B_TARGET 0x81ac042cull
#define STAGE20B_ORIG   0x97ff38d9u
#elif defined(CACTUS_STAGE85_NATIVE) && CACTUS_STAGE85_NATIVE
#define STAGE20B_TARGET 0x81ac042cull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE84_NATIVE) && CACTUS_STAGE84_NATIVE
#define STAGE20B_TARGET 0x81ac01ecull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE83_NATIVE) && CACTUS_STAGE83_NATIVE
#define STAGE20B_TARGET 0x81ac000cull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE82_NATIVE) && CACTUS_STAGE82_NATIVE
#define STAGE20B_TARGET 0x81abfd0cull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE81_NATIVE) && CACTUS_STAGE81_NATIVE
#define STAGE20B_TARGET 0x81abfb6cull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE80_NATIVE) && CACTUS_STAGE80_NATIVE
#define STAGE20B_TARGET 0x81abfafcull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE79_NATIVE) && CACTUS_STAGE79_NATIVE
#define STAGE20B_TARGET 0x81abebacull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
#define STAGE20B_TARGET 0x81abea6cull
#define STAGE20B_ORIG 0xf9400108u
#elif defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
#define STAGE20B_TARGET 0x81ac442cull
#define STAGE20B_ORIG 0x90ffaca1u
#elif defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
#define STAGE20B_TARGET 0x81ac430cull
#define STAGE20B_ORIG 0x90ffaca1u
#elif defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
#define STAGE20B_TARGET 0x81ac42ecull
#define STAGE20B_ORIG 0x90ffaca1u
#elif defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
#define STAGE20B_TARGET 0x81ac3fccull
#define STAGE20B_ORIG 0xb0ffaca1u
#elif defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
#define STAGE20B_TARGET 0x81ac3e4cull
#define STAGE20B_ORIG 0xb0ffaca1u
#elif defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
#define STAGE20B_TARGET 0x81ac3e0cull
#define STAGE20B_ORIG 0xb0ffaca1u
#elif defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
#define STAGE20B_TARGET 0x81ac3e2cull
#define STAGE20B_ORIG 0xb0ffaca1u
#elif defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
#define STAGE20B_TARGET 0x81ac3fccull
#define STAGE20B_ORIG 0xb0ffaca1u
#elif defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
#define STAGE20B_TARGET 0x81ac400cull
#define STAGE20B_ORIG 0x90ffaca1u
#elif defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
#define STAGE20B_TARGET 0x81ac3e0cull
#define STAGE20B_ORIG 0xb0ffaca1u
#elif defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
#define STAGE20B_TARGET 0x81ac3cecull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
#define STAGE20B_TARGET 0x81ac3b5cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
#define STAGE20B_TARGET 0x81ac393cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
#define STAGE20B_TARGET 0x81ac38acull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
#define STAGE20B_TARGET 0x81ac389cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
#define STAGE20B_TARGET 0x81ac377cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
#define STAGE20B_TARGET 0x81ac369cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
#define STAGE20B_TARGET 0x81ac336cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
#define STAGE20B_TARGET 0x81ac318cull
#define STAGE20B_ORIG   0xb0ffaca1u
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
#define STAGE20B_TARGET 0x81ac30dcull
#define STAGE20B_ORIG   0xd0ffaca1u
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
#define STAGE20B_TARGET 0x81ac307cull
#define STAGE20B_ORIG   0xd0ffaca1u
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
#define STAGE20B_TARGET 0x81ac2f2cull
#define STAGE20B_ORIG   0xf0ffaca1u /* Stage53 small-font C continuation */
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
#define STAGE20B_TARGET 0x81ac3c2cull
#define STAGE20B_ORIG   0xd0ffaca1u /* Stage52 native early-C join */
#else
#define STAGE20B_TARGET (0x81ac0c0cull+STAGE51_EARLY_C_OFFSET)
#define STAGE20B_ORIG   0xb0ffacc1u /* adrp x1, early kernel data */
#endif
#define STAGE20B_BRK    0xd421c480u /* brk #0xe24 */
#define STAGE20B_IMM    0xe24u
#define STAGE20B_ARM_EVENT 0x2204u
#define STAGE20B_TRAP_EVENT 0x2206u
#define STAGE20B_RESTORE_EVENT 0x220bu
#if defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac442cull
#elif defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac430cull
#elif defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac42ecull
#elif defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3fccull
#elif defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3e4cull
#elif defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3e0cull
#elif defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3e2cull
#elif defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3fccull
#elif defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac400cull
#elif defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3e0cull
#elif defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3cecull
#elif defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac3b5cull
#elif defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
#define STAGE22_TARGET_VA 0xfffffff007ac393cull
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
#define STAGE22_TARGET_VA 0xfffffff007ac38acull
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
#define STAGE22_TARGET_VA 0xfffffff007ac389cull
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
#define STAGE22_TARGET_VA 0xfffffff007ac377cull
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
#define STAGE22_TARGET_VA 0xfffffff007ac369cull
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
#define STAGE22_TARGET_VA 0xfffffff007ac336cull
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
#define STAGE22_TARGET_VA 0xfffffff007ac318cull
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
#define STAGE22_TARGET_VA 0xfffffff007ac30dcull
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
#define STAGE22_TARGET_VA 0xfffffff007ac307cull
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
#define STAGE22_TARGET_VA 0xfffffff007ac2f2cull
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
#define STAGE22_TARGET_VA 0xfffffff007ac3c2cull
#else
#define STAGE22_TARGET_VA (0xfffffff007ac0c0cull+STAGE51_EARLY_C_OFFSET)
#endif
#endif
#elif defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
#define STAGE20B_TARGET 0x81ac061cull
#define STAGE20B_ORIG   0xa903ffffu /* stp xzr,xzr,[sp,#48] */
#define STAGE20B_BRK    0xd421c460u /* brk #0xe23 */
#define STAGE20B_IMM    0xe23u
#define STAGE20B_ARM_EVENT 0x21e0u
#define STAGE20B_TRAP_EVENT 0x21e1u
#define STAGE20B_RESTORE_EVENT 0x21e8u
#define STAGE21D_TARGET_VA 0xfffffff007ac061cull
#elif defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
#define STAGE20B_TARGET 0x8142f490ull
#define STAGE20B_ORIG   0xd2a00600u /* movz x0, #0x30, lsl #16 */
#define STAGE20B_BRK    0xd421c440u /* brk #0xe22 */
#define STAGE20B_IMM    0xe22u
#define STAGE20B_ARM_EVENT 0x21d0u
#define STAGE20B_TRAP_EVENT 0x21d1u
#define STAGE20B_RESTORE_EVENT 0x21d7u
#elif defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
#define STAGE20B_TARGET 0x8142f474ull
#define STAGE20B_ORIG   0xd518c000u /* msr vbar_el1, x0 */
#define STAGE20B_BRK    0xd421c420u /* brk #0xe21 */
#define STAGE20B_IMM    0xe21u
#define STAGE20B_ARM_EVENT 0x21c0u
#define STAGE20B_TRAP_EVENT 0x21c1u
#define STAGE20B_RESTORE_EVENT 0x21c5u
#else
#define STAGE20B_TARGET 0x8142f154ull
#define STAGE20B_ORIG   0xf0ffea59u /* adrp x25, 0x8117a000 */
#define STAGE20B_BRK    0xd421a400u /* brk #0xd20 */
#define STAGE20B_IMM    0xd20u
#define STAGE20B_ARM_EVENT 0x20d0u
#define STAGE20B_TRAP_EVENT 0x20d1u
#define STAGE20B_RESTORE_EVENT 0x20d5u
#endif
#if defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
#define STAGE20D_VECTOR_BASE (0x81429000ull+STAGE52_NATIVE_SHIFT)
#define STAGE21C2_VBAR_VA (0xfffffff007429000ull+STAGE52_NATIVE_SHIFT)
#else
#define STAGE20D_VECTOR_BASE 0x8142e000ull
#endif
#if defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
#define STAGE20D_SYNC_SLOT STAGE20D_VECTOR_BASE /* EL1t */
#else
#define STAGE20D_SYNC_SLOT (STAGE20D_VECTOR_BASE+0x200ull)
#endif
static const uint32_t stage20d_after_vbar[4] = {
    0xf9400696u, 0xf9400a97u, 0xf9400e98u,
#if defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
    0x90ffea79u /* Xcode Stage78 ADRP at native 0x8142e154 */
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE && !defined(CACTUS_STAGE53_LIVE_CONSOLE)
    0x90ffea59u
#else
    0xf0ffea59u
#endif
};
/* The ELF is linked at zero but loaded at a physical runtime address.
 * Resolve the handler with ADR at runtime, never an absolute link address. */
#if !defined(CACTUS_STAGE21C1) || !CACTUS_STAGE21C1
extern uintptr_t stage20d_vector_handler_address(void);
#endif
static uint32_t stage20d_vector_saved[
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    8
#else
    4
#endif
];
static unsigned stage20d_vector_armed;
#else
#define STAGE20B_TARGET 0x8142f144ull
#define STAGE20B_ORIG   0xd518c000u /* msr vbar_el1, x0 */
#define STAGE20B_BRK    0xd4218400u /* brk #0xc20 */
#define STAGE20B_IMM    0xc20u
#define STAGE20B_ARM_EVENT 0x20c0u
#define STAGE20B_TRAP_EVENT 0x20c1u
#define STAGE20B_RESTORE_EVENT 0x20c3u
#endif
#define STAGE20C_FB_FIRST 0x5e9e3000ull
#define STAGE20C_FB_LAST  (STAGE20C_FB_FIRST+31u*2880u+63u*4u)
#define STAGE20C_FB_BASE 0x5e605000ull
#define STAGE20C_FB_SIZE 0x17bb000ull
/* Exact 23 A64 instructions from the verified relocated SWEETXNU. */
static const uint32_t stage20c_early[23] = {
    0xd510109f, 0xd5034fdf, 0xaa0003f4, 0xd2800015,
#if defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
    0xf2e00000, 0xf2c00000, 0xf2aff160, 0xf2920000,
#else
    0xf2e00000, 0xf2c00000, 0xf2abd3c0, 0xf2860000,
#endif
    0x12800001, 0xd2800402, 0xd2816804, 0xd2800803,
    0xaa0003e5, 0xb80044a1, 0xf1000463, 0x54ffffc1,
    0x8b040000, 0xf1000442, 0x54ffff21, 0xd5033f9f,
    0xf0ffffe0, 0x91000000, 0xd518c000
};
#else
#define STAGE20B_TARGET 0x8142f0ecull
#define STAGE20B_ORIG   0xd510109fu
#define STAGE20B_BRK    0xd4216400u  /* brk #0xb20 */
#define STAGE20B_IMM    0xb20u
#define STAGE20B_ARM_EVENT 0x20b0u
#define STAGE20B_TRAP_EVENT 0x20b2u
#define STAGE20B_RESTORE_EVENT 0x20b4u
#endif
#define STAGE20B_BRANCH 0x14000719u
static uint32_t stage20b_saved;
#if defined(CACTUS_STAGE25) && CACTUS_STAGE25
/* BL _pmap_map_bd.cold.1 at the null-PTE failure join. On cactus the
 * Stage24 hardware panic reached this path. At the join x19 = failing
 * virtual address, x20 = requested VA, x21 = physical end, and x22 =
 * physical start, all retained from pmap_map_bd's function prologue. */
#define STAGE25_PMAP_PA  0x81405218ull
#define STAGE25_PMAP_VA  0xfffffff007405218ull
#define STAGE25_PMAP_ORIG 0x941ae25eu
#define STAGE25_PMAP_BRK  0xd421c4a0u /* brk #0xe25 */
static uint32_t stage25_pmap_saved;
static unsigned stage25_pmap_armed;
#endif
static volatile unsigned stage20b_trap_ok, stage20b_hvc_ok;
static void stage20b_sync_instruction(uintptr_t pa)
{
    /* Publish patched/restored instruction from D-cache to I-cache. */
    __asm__ volatile("dc cvau, %0; dsb sy; ic ivau, %0; dsb sy; isb"
                     : : "r"(pa) : "memory");
}
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
static void stage20d_restore_vector(void)
{
    if(!stage20d_vector_armed) return;
    volatile uint32_t *const slot=(void *)(uintptr_t)STAGE20D_SYNC_SLOT;
    for(unsigned i=0;i<4u;i++) slot[i]=stage20d_vector_saved[i];
    stage20b_sync_instruction((uintptr_t)STAGE20D_SYNC_SLOT);
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    volatile uint32_t *const el1h=(void *)(uintptr_t)(STAGE20D_VECTOR_BASE+0x200u);
    for(unsigned i=0;i<4u;i++) el1h[i]=stage20d_vector_saved[i+4];
    stage20b_sync_instruction((uintptr_t)(STAGE20D_VECTOR_BASE+0x200u));
#endif
    stage20d_vector_armed=0;
}
static unsigned stage20d_vector_is_original(void)
{
    const volatile uint32_t *const slot=(const void *)(uintptr_t)STAGE20D_SYNC_SLOT;
#if defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
    const unsigned el1t_original=slot[0]==0x14000400u && slot[1]==0xd503201fu &&
           slot[2]==0xd503201fu && slot[3]==0xd503201fu;
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    const volatile uint32_t *const el1h=(const void *)(uintptr_t)(STAGE20D_VECTOR_BASE+0x200u);
    return el1t_original && el1h[0]==0x140003f6u &&
           el1h[1]==0xd503201fu && el1h[2]==0xd503201fu &&
           el1h[3]==0xd503201fu;
#else
    return el1t_original;
#endif
#else
    return slot[0]==0x14000000u && slot[1]==0xd503201fu &&
           slot[2]==0xd503201fu && slot[3]==0xd503201fu;
#endif
}
static int stage20d_install_vector(void)
{
    if((STAGE20D_VECTOR_BASE&0x7ffu) ||
       !stage20d_vector_is_original()) return 0;
    volatile uint32_t *const slot=(void *)(uintptr_t)STAGE20D_SYNC_SLOT;
#if defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
    /* XNU has virtual SP_EL0 and SP_EL1 but its MMU remains disabled.
     * The EL1t vector uses HVC directly, never touching an EL1 stack.
     * EL2 receives this exception using its working physical stack. */
    const uint64_t handler=0xd4000422u; /* HVC #0x21 */
    const uint32_t stub[4] = {
        (uint32_t)handler, 0x14000000u, 0xd503201fu, 0xd503201fu
    };
#else
    const uint64_t handler=(uint64_t)stage20d_vector_handler_address();
    if(!handler || (handler&3u)) return 0;
    const uint32_t stub[4] = {
        0x58000050u, /* ldr x16, #8 */
        0xd61f0200u, /* br x16 */
        (uint32_t)handler, (uint32_t)(handler>>32)
    };
#endif
    for(unsigned i=0;i<4u;i++) stage20d_vector_saved[i]=slot[i];
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    volatile uint32_t *const el1h=(void *)(uintptr_t)(STAGE20D_VECTOR_BASE+0x200u);
    for(unsigned i=0;i<4u;i++) stage20d_vector_saved[i+4]=el1h[i];
#endif
    stage20d_vector_armed=1;
#if defined(CACTUS_STAGE22) && CACTUS_STAGE22
    mark(0x2203,STAGE20D_VECTOR_BASE,STAGE20D_VECTOR_BASE+0x200u,STAGE21C2_VBAR_VA);
#elif defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    mark(0x21e6,STAGE20D_VECTOR_BASE,STAGE20D_VECTOR_BASE+0x200u,STAGE21C2_VBAR_VA);
#elif defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
    mark(0x21d6,STAGE20D_VECTOR_BASE,STAGE21C2_VBAR_VA,handler);
#elif defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
    mark(0x21c6,STAGE20D_VECTOR_BASE,STAGE20D_SYNC_SLOT,handler);
#else
    mark(0x20d6,STAGE20D_VECTOR_BASE,STAGE20D_SYNC_SLOT,handler);
#endif
    for(unsigned i=0;i<4u;i++) slot[i]=stub[i];
    stage20b_sync_instruction((uintptr_t)STAGE20D_SYNC_SLOT);
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    for(unsigned i=0;i<4u;i++) el1h[i]=stub[i];
    stage20b_sync_instruction((uintptr_t)(STAGE20D_VECTOR_BASE+0x200u));
#endif
    for(unsigned i=0;i<4u;i++) if(slot[i]!=stub[i]) {
        stage20d_restore_vector();
        return 0;
    }
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    for(unsigned i=0;i<4u;i++) if(el1h[i]!=stub[i]) {
        stage20d_restore_vector();
        return 0;
    }
#endif
    return 1;
}
#endif
static int stage20b_arm(void)
{
#if defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
    /* Stage78 Xcode 16 rebased boot0 and rewrote arm_init. Use the exact
     * SHA-pinned Stage78 instruction profile before enabling native EL1. */
    if (loaded_entry_pa != 0x8142c488ull ||
#if defined(CACTUS_STAGE96_NATIVE) && CACTUS_STAGE96_NATIVE
        loaded_boot_args_pa != 0x834c0000ull) return 0;
#elif defined(CACTUS_STAGE95_NATIVE) && CACTUS_STAGE95_NATIVE
        loaded_boot_args_pa != 0x834c0000ull) return 0;
#elif defined(CACTUS_STAGE91_NATIVE) && CACTUS_STAGE91_NATIVE
        loaded_boot_args_pa != 0x834c0000ull) return 0;
#elif defined(CACTUS_STAGE90_NATIVE) && CACTUS_STAGE90_NATIVE
        loaded_boot_args_pa != 0x834c0000ull) return 0;
#elif defined(CACTUS_STAGE89_NATIVE) && CACTUS_STAGE89_NATIVE
        loaded_boot_args_pa != 0x834c0000ull) return 0;
#elif defined(CACTUS_STAGE86_NATIVE) && CACTUS_STAGE86_NATIVE
        loaded_boot_args_pa != 0x834bc000ull) return 0;
#elif defined(CACTUS_STAGE80_NATIVE) && CACTUS_STAGE80_NATIVE
        loaded_boot_args_pa != 0x824c4000ull) return 0;
#else
        loaded_boot_args_pa != 0x824c0000ull) return 0;
#endif
    static const struct { uintptr_t pa; uint32_t word; } pinned[] = {
        {0x8142c488ull,0x14000719u},
        {0x8142e0ecull,0xd510109fu},
        {0x8142e0f0ull,0xd5034fdfu},
        {0x8142e174ull,0xd50041bfu},
        {0x8142e18cull,0xd50040bfu},
        {0x8142e220ull,0xd355ff05u},
        {0x8142e3d8ull,0xd5182041u},
#if defined(CACTUS_STAGE96_NATIVE) && CACTUS_STAGE96_NATIVE
        {0x8142e3e4ull,CACTUS96_WORD_8142E3E4},
#else
        {0x8142e3e4ull,0x940012f0u},
#endif
        {0x8142e3f4ull,0xd5182020u},
        {0x8142e43cull,0xd518a200u},
        {0x8142e494ull,0xd5181000u},
        {0x8142e498ull,0xd5033fdfu},
#if defined(CACTUS_STAGE96_NATIVE) && CACTUS_STAGE96_NATIVE
        {0x81abfdfcull,CACTUS96_WORD_81ABFDFC},
        {0x81abfe1cull,CACTUS96_WORD_81ABFE1C},
        {0x81abfe24ull,CACTUS96_WORD_81ABFE24},
        {0x81abfe2cull,CACTUS96_WORD_81ABFE2C},
        {0x81ac042cull,CACTUS96_WORD_81AC042C},
#elif defined(CACTUS_STAGE95_NATIVE) && CACTUS_STAGE95_NATIVE
        {0x81abfdfcull,0x91012400u},
        {0x81abfe1cull,0x913a5400u},
        {0x81abfe24ull,0xb0ffade2u},
        {0x81abfe2cull,0x97ff3c09u},
        {0x81ac042cull,0x913a5400u},
#elif defined(CACTUS_STAGE91_NATIVE) && CACTUS_STAGE91_NATIVE
        {0x81abfdfcull,0x913e0d29u},
        {0x81abfe1cull,0x913e0c00u},
        {0x81abfe24ull,0x90ffade2u},
        {0x81abfe2cull,0x97ff3b99u},
        {0x81ac042cull,0x913e0d29u},
#elif defined(CACTUS_STAGE90_NATIVE) && CACTUS_STAGE90_NATIVE
        {0x81abfdfcull,0x97ff3b65u},
        {0x81abfe1cull,0x97ff3b5du},
        {0x81abfe24ull,0x910003fdu},
        {0x81abfe2cull,0x9107dc00u},
        {0x81ac042cull,0x9107dc00u},
#elif defined(CACTUS_STAGE89_NATIVE) && CACTUS_STAGE89_NATIVE
        {0x81abfdfcull,0x97ff3a65u},
        {0x81abfe1cull,0x5280006bu},
        {0x81abfe24ull,0xb0ffade8u},
        {0x81abfe2cull,0x92403c09u},
        {0x81ac042cull,0x97ff38d9u},
#elif defined(CACTUS_STAGE85_NATIVE) && CACTUS_STAGE85_NATIVE
        {0x81abfdfcull,0xd10343ffu},
        {0x81abfe1cull,0xf0000a68u},
        {0x81abfe24ull,0xf0ffade1u},
        {0x81abfe2cull,0x52800020u},
        {0x81ac042cull,0xf9400108u},
#elif defined(CACTUS_STAGE84_NATIVE) && CACTUS_STAGE84_NATIVE
        {0x81abfbbCull,0xd10343ffu},
        {0x81abfbdcull,0xf0000a68u},
        {0x81abfbe4ull,0xf0ffade1u},
        {0x81abfbecull,0x52800020u},
        {0x81ac01ecull,0xf9400108u},
#elif defined(CACTUS_STAGE83_NATIVE) && CACTUS_STAGE83_NATIVE
        {0x81abf9dcull,0xd10343ffu},
        {0x81abf9fcull,0xf0000a68u},
        {0x81abfa04ull,0xf0ffade1u},
        {0x81abfa0cull,0x52800020u},
        {0x81ac000cull,0xf9400108u},
#elif defined(CACTUS_STAGE82_NATIVE) && CACTUS_STAGE82_NATIVE
        {0x81abf6dcull,0xd10343ffu},
        {0x81abf6fcull,0xf0000a68u},
        {0x81abf704ull,0xf0ffade1u},
        {0x81abf70cull,0x52800020u},
        {0x81abfd0cull,0xf9400108u},
#elif defined(CACTUS_STAGE81_NATIVE) && CACTUS_STAGE81_NATIVE
        {0x81abf53cull,0xd10343ffu},
        {0x81abf55cull,0xf0000a68u},
        {0x81abf564ull,0xf0ffade1u},
        {0x81abf56cull,0x52800020u},
        {0x81abfb6cull,0xf9400108u},
#elif defined(CACTUS_STAGE80_NATIVE) && CACTUS_STAGE80_NATIVE
        {0x81abf4ccull,0xd10343ffu},
        {0x81abf4ecull,0xf0000a68u},
        {0x81abf4f4ull,0xf0ffade1u},
        {0x81abf4fcull,0x52800020u},
        {0x81abfafcull,0xf9400108u},
#elif defined(CACTUS_STAGE79_NATIVE) && CACTUS_STAGE79_NATIVE
        {0x81abe57cull,0xd10343ffu},
        {0x81abe59cull,0x90000a68u},
        {0x81abe5a4ull,0x90ffae01u},
        {0x81abe5acull,0x52800020u},
        {0x81abebacull,0xf9400108u},
#else
        {0x81abe43cull,0xd10343ffu},
        {0x81abe45cull,0x90000a68u},
        {0x81abe464ull,0xb0ffae01u},
        {0x81abe46cull,0x52800020u},
        {0x81abea6cull,0xf9400108u},
#endif
    };
    for (unsigned i=0;i<sizeof(pinned)/sizeof(pinned[0]);i++)
        if (*(volatile const uint32_t *)(uintptr_t)pinned[i].pa != pinned[i].word)
            return 0;
    for (unsigned i=0;i<23u;i++)
        if (*(volatile const uint32_t *)(uintptr_t)(STAGE20B_ENTRY_TARGET+4u*i)
            != stage20c_early[i]) return 0;
    for (unsigned i=0;i<4u;i++)
        if (*(volatile const uint32_t *)(uintptr_t)
             (0x8142f148ull+STAGE52_NATIVE_SHIFT+4u*i) != stage20d_after_vbar[i])
            return 0;
    stage20b_saved = *(volatile const uint32_t *)(uintptr_t)STAGE20B_TARGET;
    stage20b_trap_ok = 0;
    stage20b_hvc_ok = 0;
    if (!stage20d_install_vector()) return 0;
    mark(STAGE20B_ARM_EVENT, loaded_entry_pa, STAGE20B_TARGET,
        *(volatile const uint32_t *)(uintptr_t)loaded_entry_pa);
    /* Stage23 native pass-through: do not replace any C opcode with BRK. */
    return 1;
#else
    if(loaded_entry_pa!=STAGE20B_ENTRY ||
       loaded_boot_args_pa!=(0x824bc000ull+
#if defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
           0xc000ull
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
           0x4000ull
#else
           0ull
#endif
       ))
        return 0;
    const uint32_t branch=*(volatile const uint32_t *)(uintptr_t)loaded_entry_pa;
    if(branch!=STAGE20B_BRANCH ||
       loaded_entry_pa + ((uint64_t)(branch & 0x03ffffffu)<<2) !=
           STAGE20B_ENTRY_TARGET)
        return 0;
#if defined(CACTUS_STAGE20C) && CACTUS_STAGE20C
    /* Verify the exact XNU path up to its VBAR handoff before patching. */
    for(unsigned i=0;i<23u;i++)
        if(*(volatile const uint32_t *)(uintptr_t)
           (STAGE20B_ENTRY_TARGET+4u*i) != stage20c_early[i])
            return 0;
    const volatile struct boot_args *ba=(const void *)(uintptr_t)loaded_boot_args_pa;
    if(ba->Video.v_baseAddr!=STAGE20C_FB_BASE ||
       ba->Video.v_rowBytes!=2880u || ba->Video.v_width!=720u ||
       ba->Video.v_height!=1440u || ba->Video.v_depth!=32u ||
       STAGE20C_FB_FIRST<STAGE20C_FB_BASE ||
       STAGE20C_FB_LAST+4u>STAGE20C_FB_BASE+STAGE20C_FB_SIZE)
        return 0;
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
    for(unsigned i=0;i<4u;i++)
        if(*(volatile const uint32_t *)(uintptr_t)(0x8142f148ull+STAGE52_NATIVE_SHIFT+4u*i)
           !=stage20d_after_vbar[i]) return 0;
#if defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
    /* Pin the exact opcode sequence surrounding MMU enable and ISB. */
    if(*(volatile const uint32_t *)(uintptr_t)(0x8142f474ull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT)!=0xd518c000u ||
       *(volatile const uint32_t *)(uintptr_t)(0x8142f488ull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT)!=0xd5181000u ||
       *(volatile const uint32_t *)(uintptr_t)(0x8142f48cull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT)!=0xd5033fdfu)
        return 0;
#endif
#if defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    /* Guard the first C routine's exact stack prologue and memory ops
     * before permitting a high-VA breakpoint in copied XNU code. */
    static const uint32_t c_entry[]={
        0xd10343ffu,0xa9076ffcu,0xa90867fau,0xa9095ff8u,
        0xa90a57f6u,0xa90b4ff4u,0xa90c7bfdu,0x910303fdu,
#if defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
        0xf0000a68u,0xaa0003f3u,0x90ffade1u,
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
        0xf0000a68u,0xaa0003f3u,0xb0ffade1u,
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
        0xf0000a68u,0xaa0003f3u,0xb0ffade1u,
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
        0xf0000a68u,0xaa0003f3u,0xb0ffade1u,
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
        0xf0000a68u,0xaa0003f3u,0xb0ffade1u,
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
        0x90000a88u,0xaa0003f3u,0xd0ffade1u,
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
        0x90000a88u,0xaa0003f3u,0xd0ffade1u,
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
        0x90000a88u,0xaa0003f3u,0xd0ffade1u,
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
        0x90000a88u,0xaa0003f3u,0xd0ffade1u,
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
        0x90000a88u,0xaa0003f3u,0xd0ffade1u,
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
        0xf0000a68u,0xaa0003f3u,0xb0ffade1u,
#else
        0xd0000a68u,0xaa0003f3u,0x90ffae01u,
#endif
#if defined(CACTUS_STAGE27) && CACTUS_STAGE27
#if defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
        0x91203821u,
#elif defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
        0x91203821u,
#elif defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
        0x91213821u,
#elif defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
        0x9123b821u,
#elif defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
        0x9123b821u,
#elif defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
        0x9128b821u,
#elif defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
        0x9128b821u,
#elif defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
        0x9126b821u,
#elif defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
        0x9125b821u,
#elif defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
        0x91373821u,
#elif defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
        0x913eb821u,
#elif defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
        0x9100b821u,
#elif defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
        0x91023821u,
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
        0x91053821u,
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
        0x9108b821u,
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
        0x910b3821u,
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
        0x910e3821u,
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
        0x9113b821u,
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
        0x9117b821u,
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
        0x911c1c21u,
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
        0x911ce021u,
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
        0x911e9c21u,
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
        0x9136f021u,
#else
        0x913cf021u,
#endif
#else
        0x91353021u,
#endif
        0x52800020u,0xd503201fu,0xf9459108u,0xf81a83a8u
    };
    for(unsigned i=0;i<sizeof(c_entry)/sizeof(c_entry[0]);i++)
        if(*(volatile const uint32_t *)(uintptr_t)
           (0x81ac05dcull+STAGE51_EARLY_C_OFFSET+STAGE53_C_SHIFT+STAGE54_C_SHIFT+STAGE55_C_SHIFT+STAGE56_C_SHIFT+STAGE57_C_SHIFT+STAGE58_C_SHIFT+STAGE59_C_SHIFT+STAGE60_C_SHIFT+STAGE61_C_SHIFT+STAGE63_C_SHIFT+STAGE65_C_SHIFT+STAGE67_C_SHIFT+STAGE68_C_SHIFT+STAGE69_C_SHIFT+STAGE70_C_SHIFT+STAGE71_C_SHIFT+STAGE72_C_SHIFT+STAGE73_C_SHIFT+STAGE74_C_SHIFT+STAGE75_C_SHIFT+STAGE76_C_SHIFT+STAGE77_C_SHIFT+STAGE52_NATIVE_SHIFT+4u*i)!=c_entry[i]) return 0;
#endif
#if defined(CACTUS_STAGE22) && CACTUS_STAGE22
    /* The branch into this later C checkpoint follows two early calls,
     * a relocation/header path and several additional startup calls.
     * Refuse the image if any pinned instruction or join moved. */
    static const uintptr_t pcs[]={
        0x81ac0624ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0628ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0638ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0668ull+STAGE51_EARLY_C_OFFSET,
        0x81ac06ecull+STAGE51_EARLY_C_OFFSET,
        0x81ac0b9cull+STAGE51_EARLY_C_OFFSET,
        0x81ac0ba0ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0bf8ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0bfcull+STAGE51_EARLY_C_OFFSET,
        0x81ac0c00ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0c04ull+STAGE51_EARLY_C_OFFSET,
        0x81ac0c08ull+STAGE51_EARLY_C_OFFSET
    };
    static const uint32_t stage22_words[]={
#if defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
        0x97e585cfu,0x97e57cb2u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e575e1u,0x90ffb608u,0x97e5c0f2u,
        0x97e5bdb5u,0x97e5bd9cu,0x97e5c0e7u,0x97e5c0eau
#elif defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
        0x97e58617u,0x97e57cfau,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57629u,0x90ffb608u,0x97e5c13au,
        0x97e5bdfdu,0x97e5bde4u,0x97e5c12fu,0x97e5c132u
#elif defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
        0x97e5861fu,0x97e57d02u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57631u,0x90ffb608u,0x97e5c142u,
        0x97e5be05u,0x97e5bdecu,0x97e5c137u,0x97e5c13au
#elif defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
        0x97e586e7u,0x97e57dcau,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e576f9u,0xb0ffb608u,0x97e5c20au,
        0x97e5becdu,0x97e5beb4u,0x97e5c1ffu,0x97e5c202u
#elif defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
        0x97e58747u,0x97e57e2au,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57759u,0xb0ffb608u,0x97e5c26au,
        0x97e5bf2du,0x97e5bf14u,0x97e5c25fu,0x97e5c262u
#elif defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
        0x97e58757u,0x97e57e3au,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57769u,0xb0ffb608u,0x97e5c27au,
        0x97e5bf3du,0x97e5bf24u,0x97e5c26fu,0x97e5c272u
#elif defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
        0x97e5874fu,0x97e57e32u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57761u,0xb0ffb608u,0x97e5c272u,
        0x97e5bf35u,0x97e5bf1cu,0x97e5c267u,0x97e5c26au
#elif defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
        0x97e586e7u,0x97e57dcau,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e576f9u,0xb0ffb608u,0x97e5c20au,
        0x97e5becdu,0x97e5beb4u,0x97e5c1ffu,0x97e5c202u
#elif defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
        0x97e586d7u,0x97e57dbau,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e576e9u,0xb0ffb608u,0x97e5c1fau,
        0x97e5bebdu,0x97e5bea4u,0x97e5c1efu,0x97e5c1f2u
#elif defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
        0x97e58757u,0x97e57e3au,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57769u,0xb0ffb608u,0x97e5c27au,
        0x97e5bf3du,0x97e5bf24u,0x97e5c26fu,0x97e5c272u
#elif defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
        0x97e5879fu,0x97e57e82u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e577b1u,0xb0ffb608u,0x97e5c2c2u,
        0x97e5bf85u,0x97e5bf6cu,0x97e5c2b7u,0x97e5c2bau
#elif defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
        0x97e58803u,0x97e57ee6u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57815u,0xb0ffb608u,0x97e5c326u,
        0x97e5bfe9u,0x97e5bfd0u,0x97e5c31bu,0x97e5c31eu
#elif defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
        0x97e5888bu,0x97e57f6eu,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e5789du,0xb0ffb608u,0x97e5c3aeu,
        0x97e5c071u,0x97e5c058u,0x97e5c3a3u,0x97e5c3a6u
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
        0x97e588afu,0x97e57f92u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e578c1u,0xb0ffb608u,0x97e5c3d2u,
        0x97e5c095u,0x97e5c07cu,0x97e5c3c7u,0x97e5c3cau
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
        0x97e588b3u,0x97e57f96u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e578c5u,0xb0ffb608u,0x97e5c3d6u,
        0x97e5c099u,0x97e5c080u,0x97e5c3cbu,0x97e5c3ceu
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
        0x97e588fbu,0x97e57fdeu,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e5790du,0xb0ffb608u,0x97e5c41eu,
        0x97e5c0e1u,0x97e5c0c8u,0x97e5c413u,0x97e5c416u
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
        0x97e58933u,0x97e58016u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57945u,0xb0ffb608u,0x97e5c456u,
        0x97e5c119u,0x97e5c100u,0x97e5c44bu,0x97e5c44eu
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
        0x97e589ffu,0x97e580e2u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57a11u,0xb0ffb608u,0x97e5c522u,
        0x97e5c1e5u,0x97e5c1ccu,0x97e5c517u,0x97e5c51au
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
        0x97e58a77u,0x97e5815au,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57a89u,0xb0ffb608u,0x97e5c59au,
        0x97e5c25du,0x97e5c244u,0x97e5c58fu,0x97e5c592u
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
        0x97e58aa3u,0x97e58186u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57ab5u,0xb0ffb608u,0x97e5c5bau,
        0x97e5c27du,0x97e5c264u,0x97e5c5afu,0x97e5c5b2u
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
        0x97e58abbu,0x97e5819eu,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57acdu,0xb0ffb608u,0x97e5c5d2u,
        0x97e5c295u,0x97e5c27cu,0x97e5c5c7u,0x97e5c5cau
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
        0x97e58b0fu,0x97e581f2u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57b21u,0xd0ffb608u,0x97e5c626u,
        0x97e5c2e9u,0x97e5c2d0u,0x97e5c61bu,0x97e5c61eu
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
        0x97e5877fu,0x97e57e62u,0x37f805c9u,0x540029c0u,
        0x1400012du,0x97e57791u,0xb0ffb608u,0x97e5cee6u,
        0x97e5cba9u,0x97e5cb90u,0x97e5cedbu,0x97e5cedeu
#else
#if defined(CACTUS_STAGE27) && CACTUS_STAGE27
#if defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
        0x97e5937fu,
#else
        0x97e59383u,
#endif
#else
        0x97e59363u,
#endif
#if defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
        0x97e58a62u,0x37f805c9u,
#else
        0x97e58a6au,0x37f805c9u,
#endif
        0x540029c0u,0x1400012du,
#if defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
        0x97e58391u,
#else
        0x97e58399u,
#endif
        0x90ffb628u,0x97e5cee6u,0x97e5cba9u,
        0x97e5cb90u,0x97e5cedbu,0x97e5cedeu
#endif
    };
    for(unsigned i=0;i<sizeof(pcs)/sizeof(pcs[0]);i++)
        if(*(volatile const uint32_t *)(uintptr_t)(pcs[i]+STAGE53_C_SHIFT+STAGE54_C_SHIFT+STAGE55_C_SHIFT+STAGE56_C_SHIFT+STAGE57_C_SHIFT+STAGE58_C_SHIFT+STAGE59_C_SHIFT+STAGE60_C_SHIFT+STAGE61_C_SHIFT+STAGE63_C_SHIFT+STAGE65_C_SHIFT+STAGE67_C_SHIFT+STAGE68_C_SHIFT+STAGE69_C_SHIFT+STAGE70_C_SHIFT+STAGE71_C_SHIFT+STAGE72_C_SHIFT+STAGE73_C_SHIFT+STAGE74_C_SHIFT+STAGE75_C_SHIFT+STAGE76_C_SHIFT+STAGE77_C_SHIFT+STAGE52_NATIVE_SHIFT)!=stage22_words[i])
            return 0;
#endif
#if defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
    static const uintptr_t pins[8]={
        0x8142f174ull+STAGE52_NATIVE_SHIFT,
        0x8142f18cull+STAGE52_NATIVE_SHIFT,
        0x8142f220ull+STAGE52_NATIVE_SHIFT,
        0x8142f3ccull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT,
        0x8142f3e8ull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT,
        0x8142f430ull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT,
        0x8142f450ull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT,
        0x8142f488ull+STAGE51_MMU_OFFSET+STAGE52_NATIVE_SHIFT
    };
    static const uint32_t words[8]={
        0xd50041bfu,0xd50040bfu,0xd355ff05u,0xd5182041u,
        0xd5182020u,0xd518a200u,0xb40000b5u,0xd5181000u
    };
    for(unsigned i=0;i<8u;i++)
        if(*(volatile const uint32_t *)(uintptr_t)pins[i]!=words[i])
            return 0;
    if(*(volatile const uint64_t *)(uintptr_t)0x81178a18ull!=
       0x22a5192519ull) return 0;
#endif
    if(!stage20d_install_vector()) return 0;
#endif
#endif
    const uint32_t original=
        *(volatile const uint32_t *)(uintptr_t)STAGE20B_TARGET;
    if(original!=STAGE20B_ORIG) {
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
        stage20d_restore_vector();
#endif
        return 0;
    }
    stage20b_saved=original;
    stage20b_trap_ok=0;
    stage20b_hvc_ok=0;
    mark(STAGE20B_ARM_EVENT,loaded_entry_pa,STAGE20B_TARGET,branch);
#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
    /* Stage23 runs native XNU past the Stage22 stop. The target is
     * checked above but NEVER replaced with a synthetic BRK. Only the
     * two synchronous vectors remain instrumented for genuine faults. */
    mark(0x2300,STAGE20B_TARGET,STAGE20B_ORIG,
         *(volatile const uint32_t *)(uintptr_t)STAGE20B_TARGET);
#if defined(CACTUS_STAGE36_CHECKPOINT) && CACTUS_STAGE36_CHECKPOINT
    /* Verified Stage22 code join, with a deliberate, reversible BRK.
     * If XNU reaches this address, EL1's synchronous vector returns to
     * the shim's EL2 HVC recorder. No framebuffer fix is claimed. */
    *(volatile uint32_t *)(uintptr_t)STAGE20B_TARGET=STAGE20B_BRK;
    stage20b_sync_instruction((uintptr_t)STAGE20B_TARGET);
    if(*(volatile const uint32_t *)(uintptr_t)STAGE20B_TARGET!=STAGE20B_BRK) {
        *(volatile uint32_t *)(uintptr_t)STAGE20B_TARGET=stage20b_saved;
        stage20b_sync_instruction((uintptr_t)STAGE20B_TARGET);
        stage20d_restore_vector();
        return 0;
    }
#if defined(CACTUS_STAGE43_NEXT_INIT) && CACTUS_STAGE43_NEXT_INIT
    mark(0x4300,STAGE20B_TARGET,STAGE20B_ORIG,STAGE20B_BRK);
#elif defined(CACTUS_STAGE44_NEXT_RETURN) && CACTUS_STAGE44_NEXT_RETURN
    mark(0x4400,STAGE20B_TARGET,STAGE20B_ORIG,STAGE20B_BRK);
#elif defined(CACTUS_STAGE41_CALLEE_ENTRY) && CACTUS_STAGE41_CALLEE_ENTRY
    mark(0x4100,STAGE20B_TARGET,STAGE20B_ORIG,STAGE20B_BRK);
#elif defined(CACTUS_STAGE42_AFTER_CALLEE) && CACTUS_STAGE42_AFTER_CALLEE
    mark(0x4200,STAGE20B_TARGET,STAGE20B_ORIG,STAGE20B_BRK);
#elif defined(CACTUS_STAGE40_LATE_C) && CACTUS_STAGE40_LATE_C
    mark(0x4000,STAGE20B_TARGET,STAGE20B_ORIG,STAGE20B_BRK);
#else
    mark(0x3600,STAGE20B_TARGET,STAGE20B_ORIG,STAGE20B_BRK);
#endif
#endif
#if defined(CACTUS_STAGE25) && CACTUS_STAGE25
    /* Vector is installed, so the first real missing-PTE call will
     * stop before XNU enters panic(). No speculative table writes. */
    stage25_pmap_armed=0;
    stage25_pmap_saved=*(volatile const uint32_t *)(uintptr_t)STAGE25_PMAP_PA;
    if(stage25_pmap_saved!=STAGE25_PMAP_ORIG) {
        stage20d_restore_vector();
        return 0;
    }
    *(volatile uint32_t *)(uintptr_t)STAGE25_PMAP_PA=STAGE25_PMAP_BRK;
    stage20b_sync_instruction(STAGE25_PMAP_PA);
    if(*(volatile const uint32_t *)(uintptr_t)STAGE25_PMAP_PA!=STAGE25_PMAP_BRK) {
        *(volatile uint32_t *)(uintptr_t)STAGE25_PMAP_PA=stage25_pmap_saved;
        stage20b_sync_instruction(STAGE25_PMAP_PA);
        stage20d_restore_vector();
        return 0;
    }
    stage25_pmap_armed=1;
    mark(0x2500,STAGE25_PMAP_PA,STAGE25_PMAP_VA,stage25_pmap_saved);
#endif
#else
    *(volatile uint32_t *)(uintptr_t)STAGE20B_TARGET=STAGE20B_BRK;
    stage20b_sync_instruction((uintptr_t)STAGE20B_TARGET);
    if(*(volatile const uint32_t *)(uintptr_t)STAGE20B_TARGET!=
       STAGE20B_BRK) {
        *(volatile uint32_t *)(uintptr_t)STAGE20B_TARGET=stage20b_saved;
        stage20b_sync_instruction((uintptr_t)STAGE20B_TARGET);
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
        stage20d_restore_vector();
#endif
        return 0;
    }
#endif
    return 1;
#endif /* CACTUS_STAGE78_NATIVE */
}
static int stage20b_restore(void)
{
#if defined(CACTUS_STAGE25) && CACTUS_STAGE25
    if(stage25_pmap_armed) {
        *(volatile uint32_t *)(uintptr_t)STAGE25_PMAP_PA=stage25_pmap_saved;
        stage20b_sync_instruction(STAGE25_PMAP_PA);
        stage25_pmap_armed=0;
    }
    const unsigned pmap_restored=
        *(volatile const uint32_t *)(uintptr_t)STAGE25_PMAP_PA==STAGE25_PMAP_ORIG;
#endif
#if !defined(CACTUS_STAGE23) || !CACTUS_STAGE23 || (defined(CACTUS_STAGE36_CHECKPOINT) && CACTUS_STAGE36_CHECKPOINT)
    *(volatile uint32_t *)(uintptr_t)STAGE20B_TARGET=stage20b_saved;
    stage20b_sync_instruction((uintptr_t)STAGE20B_TARGET);
#endif
    unsigned restored=
        *(volatile const uint32_t *)(uintptr_t)STAGE20B_TARGET ==
        STAGE20B_ORIG;
#if defined(CACTUS_STAGE25) && CACTUS_STAGE25
    restored=restored && pmap_restored;
    mark(0x2508,pmap_restored,STAGE25_PMAP_PA,stage25_pmap_saved);
#endif
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
    stage20d_restore_vector();
    restored=restored && stage20d_vector_is_original();
#endif
    mark(STAGE20B_RESTORE_EVENT,restored,stage20b_trap_ok,stage20b_hvc_ok);
    return restored && stage20b_trap_ok && stage20b_hvc_ok;
}
#endif
extern char _start[], image_end[];
#if defined(CACTUS_STAGE20) && CACTUS_STAGE20
extern void stage20_el1_transition(uintptr_t entry, uintptr_t boot_args);
#endif

static uint64_t ticks(void)
{
    uint64_t x;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(x));
    return x;
}
static void mark(unsigned event, uint64_t a, uint64_t b, uint64_t c)
{
    (void)cactus_trace_emit(event,a,b,c);
}
#if defined(CACTUS_STAGE38_WDT) && CACTUS_STAGE38_WDT
/* MT6765 top RGU, using the register/key definitions in shim/watchdog.c.
 * EL2 executes identity-mapped with the MMU off. Stage38 only reloads;
 * Stage39 explicitly changes MODE once at the checked XNU handoff. */
#define STAGE38_RGU_BASE 0x10007000ull
#define STAGE38_RGU_RELOAD_KEY 0x1971u
static unsigned stage38_wdt_enabled;
static uint64_t stage38_last_reload;
static uint32_t stage38_rgu_read(unsigned offset)
{
    return *(volatile const uint32_t *)(uintptr_t)(STAGE38_RGU_BASE+offset);
}
static void stage38_sample(unsigned event)
{
    const uint32_t mode=stage38_rgu_read(0);
    const uint32_t length=stage38_rgu_read(4);
    const uint32_t status=stage38_rgu_read(12);
    mark(event,mode,length,status);
    stage38_wdt_enabled=(mode&1u)!=0u;
    stage38_last_reload=ticks();
}
static void stage38_reload_if_enabled(void)
{
    const uint64_t now=ticks();
    if(!stage38_wdt_enabled ||
       now-stage38_last_reload<frequency) return;
    *(volatile uint32_t *)(uintptr_t)(STAGE38_RGU_BASE+8u)=
        STAGE38_RGU_RELOAD_KEY;
    __asm__ volatile("dsb sy" ::: "memory");
    stage38_last_reload=now;
    mark(0x3801,now,stage38_rgu_read(0),stage38_rgu_read(4));
}
#if defined(CACTUS_STAGE39_WDT_HANDOFF) && CACTUS_STAGE39_WDT_HANDOFF
static int stage39_disarm_before_xnu(void)
{
    const uint32_t before=stage38_rgu_read(0);
    if(!(before&1u)) {
        stage38_wdt_enabled=0;
        mark(0x3900,before,before,0);
        return 1;
    }
    /* Same WDT_MODE_KEY + clear EN sequence as shim/watchdog.c.
     * Preserve EXRST_EN, DDR_RSVD and unrelated bootloader mode bits.
     * XNU does not implement top-RGU watchdog servicing yet. */
    const uint32_t requested=(before&~1u)|0x22000000u;
    *(volatile uint32_t *)(uintptr_t)STAGE38_RGU_BASE=requested;
    __asm__ volatile("dsb sy" ::: "memory");
    const uint32_t after=stage38_rgu_read(0);
    mark(0x3900,before,after,requested);
    if(after&1u) return 0;
    stage38_wdt_enabled=0;
    return 1;
}
#endif
#endif
static void drain(unsigned milliseconds)
{
    const uint64_t start=ticks();
    const uint64_t limit=(frequency/1000u)*milliseconds;
    uint64_t beat=start;
    while(ticks()-start<limit) {
#if defined(CACTUS_STAGE38_WDT) && CACTUS_STAGE38_WDT
        stage38_reload_if_enabled();
#endif
        if(online) {
            usb_poll();
            if(usb_online() && (usb_diag[8]&1u)) {
                const uint8_t *f=cactus_trace_peek();
                if(f && usb_send_budgeted(f,CACTUS_TRACE_BYTES)==1)
                    cactus_trace_pop();
            }
        }
        uint64_t now=ticks();
        if(now-beat>=frequency) {
            beat=now;
            mark(S19_BEAT,heartbeat_count++,usb_diag[8],
                 ((uint64_t)cactus_trace_dropped()<<32)|
                 cactus_trace_pending());
        }
    }
}

#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
/* MI logo remains visible during COM25 on the physical panel, as reported
 * by the user. Test whether the *specific* LK splash RAM is being scanned
 * out, using three bright bars at x=48..335, y=80..159. The probe writes
 * a bounded 288x80 rectangle and leaves all other pixels unchanged.
 * Readback demonstrates RAM writes only; visibility is a separate test. */
static int stage23_splash_probe(void)
{
    const volatile struct boot_args *const ba=
        (const void *)(uintptr_t)loaded_boot_args_pa;
    if(ba->Video.v_baseAddr!=FB_BASE ||
       ba->Video.v_rowBytes!=FB_STRIDE ||
       ba->Video.v_width!=FB_W || ba->Video.v_height!=FB_H ||
       ba->Video.v_depth!=32 || FB_W<336u || FB_H<160u) {
        mark(0x23ee,ba->Video.v_baseAddr,ba->Video.v_rowBytes,ba->Video.v_depth);
        return 0;
    }
    volatile uint32_t *const fb=(void *)(uintptr_t)FB_BASE;
    const uint32_t colors[3]={0x00ff00ffu,0x0000ff00u,0x0000ffffu};
    for(unsigned y=80;y<160;y++) {
        for(unsigned x=48;x<336;x++)
            fb[y*FB_W+x]=colors[(x-48u)/96u];
        /* Clean dirty pixel data for display DMA (if LK really scans
         * out this buffer). Pixels outside the marker are untouched. */
        for(unsigned x=48;x<336;x+=16) {
            uintptr_t p=FB_BASE + (uintptr_t)y*FB_STRIDE + x*4u;
            __asm__ volatile("dc cvac, %0" : : "r"(p) : "memory");
        }
    }
    __asm__ volatile("dsb sy" ::: "memory");
    const uint32_t a=fb[80u*FB_W+48u];
    const uint32_t b=fb[80u*FB_W+144u];
    const uint32_t c=fb[159u*FB_W+335u];
    mark(0x2301,FB_BASE + 80u*FB_STRIDE + 48u*4u,
         ((uint64_t)a<<32)|b,c);
    mark(0x2302,((uint64_t)48u<<32)|80u,((uint64_t)288u<<32)|80u,
         (a==colors[0] && b==colors[1] && c==colors[2]));
    return a==colors[0] && b==colors[1] && c==colors[2];
}
#endif

#if defined(CACTUS_STAGE45_COMBINED) && CACTUS_STAGE45_COMBINED
/* MT6765 source: arch/arm64/boot/dts/mediatek/mt6765.dts and
 * drivers/misc/mediatek/video/mt6765/dispsys/ddp_reg_{ovl,dma}.h.
 * Inspect LK's display setup in one boot alongside native XNU progress.
 * All DDP MMIO accesses are read-only; do not reprogram the scanout. */
#define STAGE45_OVL0 0x1400b000ull
#define STAGE45_RDMA0 0x1400d000ull
static uint32_t stage45_reg(uintptr_t address)
{
    return *(volatile const uint32_t *)address;
}
static void stage45_scanout_probe(uintptr_t dtb)
{
    (void)dtb;
    const uint32_t ovl_en=stage45_reg(STAGE45_OVL0+0x00cu);
    const uint32_t ovl_src=stage45_reg(STAGE45_OVL0+0x02cu);
    const uint32_t ovl_sta=stage45_reg(STAGE45_OVL0+0x000u);
    const uint32_t ovl_roi=stage45_reg(STAGE45_OVL0+0x020u);
    const uint32_t l0_con=stage45_reg(STAGE45_OVL0+0x030u);
    const uint32_t l0_size=stage45_reg(STAGE45_OVL0+0x038u);
    const uint32_t l0_addr=stage45_reg(STAGE45_OVL0+0xf40u);
    const uint32_t l0_pitch=stage45_reg(STAGE45_OVL0+0x044u);
    mark(0x4500,STAGE45_OVL0,ovl_en,ovl_src);
    mark(0x4501,ovl_sta,ovl_roi,l0_con);
    mark(0x4502,l0_addr,l0_pitch,l0_size);
    mark(0x4503,stage45_reg(STAGE45_OVL0+0xf60u),
         stage45_reg(STAGE45_OVL0+0xf80u),
         stage45_reg(STAGE45_OVL0+0xfa0u));
    const uint32_t rdma_global=stage45_reg(STAGE45_RDMA0+0x010u);
    const uint32_t rdma_mem=stage45_reg(STAGE45_RDMA0+0x024u);
    const uint32_t rdma_addr=stage45_reg(STAGE45_RDMA0+0xf00u);
    const uint32_t rdma_pitch=stage45_reg(STAGE45_RDMA0+0x02cu);
    mark(0x4504,STAGE45_RDMA0,rdma_global,rdma_mem);
    mark(0x4505,rdma_addr,rdma_pitch,
         ((uint64_t)stage45_reg(STAGE45_RDMA0+0x014u)<<32)|
             stage45_reg(STAGE45_RDMA0+0x018u));

    /* Only write the already-tested tiny Stage23 marker if the live OVL
     * layer register agrees with the known boot-argument buffer and
     * 2880-byte stride. Other buffers remain untouched. Even a match
     * proves only the OVL register source, not visible panel scanout. */
    const unsigned ovl_layer0=(ovl_en&1u) && (ovl_src&1u);
    const unsigned known_source=ovl_layer0 &&
        l0_addr==(uint32_t)FB_BASE && (l0_pitch&0xffffu)==FB_STRIDE;
    mark(0x4506,((uint64_t)ovl_layer0<<32)|known_source,
         (uint64_t)l0_addr,FB_BASE);
    if(known_source) {
        const unsigned readback=stage23_splash_probe();
        mark(0x4507,readback,FB_BASE,FB_STRIDE);
    } else {
        mark(0x4507,0u,0u,0u);
    }
#if defined(CACTUS_STAGE47_LAYER1) && CACTUS_STAGE47_LAYER1
    /* Stage45 found that LK is scanning source addresses other than
     * boot_args.Video. Capture both layer configs before investigating
     * CPU address identity or attempting any pixel write to those
     * hardware-source addresses. No display-controller MMIO writes. */
    const uint32_t l1_con=stage45_reg(STAGE45_OVL0+0x050u);
    const uint32_t l1_size=stage45_reg(STAGE45_OVL0+0x058u);
    const uint32_t l1_off=stage45_reg(STAGE45_OVL0+0x05cu);
    const uint32_t l1_pitch=stage45_reg(STAGE45_OVL0+0x064u);
    const uint32_t l1_addr=stage45_reg(STAGE45_OVL0+0xf60u);
    mark(0x4700,l1_con,l1_size,l1_off);
    mark(0x4701,l1_addr,l1_pitch,(uint64_t)l0_addr);
    mark(0x4702,stage45_reg(STAGE45_OVL0+0x03cu),
         stage45_reg(STAGE45_OVL0+0x04cu),
         stage45_reg(STAGE45_OVL0+0x06cu));

    const uint64_t height=(l0_size>>16)&0x1fffu;
    const uint64_t span=(l0_pitch&0xffffu)*height;
    const uint64_t separation=l1_addr>=l0_addr ?
        (uint64_t)l1_addr-l0_addr : 0u;
    mark(0x4703,span,separation,
         ((uint64_t)((ovl_src>>1)&1u)<<32)|
           (span && separation==span));

    /* The FDT only reports RAM and carveout ranges; membership is
     * useful but does not establish that an OVL source is a CPU PA.
     * Do not dereference the OVL source addresses in this stage. */
    uint32_t fdt_bytes=0;
    struct fdt_info display_mem;
    unsigned flags=0;
    if(fdt_check(dtb,&fdt_bytes) && fdt_bytes<=0x100000u &&
       fdt_inspect((const void *)dtb,fdt_bytes,&display_mem)==0) {
        flags|=1u;
        const uint64_t stride0=l0_pitch&0xffffu;
        const uint64_t stride1=l1_pitch&0xffffu;
        const uint64_t s0=stride0*height;
        const uint64_t s1=stride1*(((uint64_t)l1_size>>16)&0x1fffu);
        for(unsigned i=0;i<display_mem.memory_count;i++) {
            const uint64_t base=display_mem.memory[i].base;
            const uint64_t size=display_mem.memory[i].size;
            if(s0 && l0_addr>=base && s0<=size &&
               (uint64_t)l0_addr-base<=size-s0) flags|=2u;
            if(s1 && l1_addr>=base && s1<=size &&
               (uint64_t)l1_addr-base<=size-s1) flags|=4u;
        }
        if(s0 && fdt_region_free(&display_mem,l0_addr,s0)) flags|=8u;
        if(s1 && fdt_region_free(&display_mem,l1_addr,s1)) flags|=16u;
        mark(0x4705,((uint64_t)display_mem.memory_count<<32)|
                     display_mem.reserved_count,
             s0,s1);
#if defined(CACTUS_STAGE48_RUN) && CACTUS_STAGE48_RUN
        /* Report exact overlapping FDT carveouts before deciding
         * whether the LK OVL addresses are CPU PAs or M4U IOVAs.
         * Only examine the FDT's validated range array. Never read
         * from or write to an unverified framebuffer address. */
        uint32_t overlaps0=0,overlaps1=0;
        for(unsigned i=0;i<display_mem.reserved_count;i++) {
            const struct fdt_range *r=&display_mem.reserved[i];
            const unsigned hit0=s0 && fdt_region_overlap(
                l0_addr,s0,r->base,r->size);
            const unsigned hit1=s1 && fdt_region_overlap(
                l1_addr,s1,r->base,r->size);
            if(hit0 || hit1) {
                overlaps0+=hit0;
                overlaps1+=hit1;
                mark(0x4801,((uint64_t)i<<32)|((hit1<<1)|hit0),
                     r->base,r->size);
            }
        }
        mark(0x4800,overlaps0,overlaps1,
             ((uint64_t)l0_addr<<32)|l1_addr);
#endif
    }
    mark(0x4704,flags,l0_addr,l1_addr);
    const volatile struct boot_args *const ba=
        (const void *)(uintptr_t)loaded_boot_args_pa;
    mark(0x4706,ba->Video.v_baseAddr,ba->Video.v_rowBytes,
         ((uint64_t)ba->Video.v_height<<32)|ba->Video.v_width);
#if defined(CACTUS_STAGE48_RUN) && CACTUS_STAGE48_RUN
    /* Last known Stage47 artificial checkpoint must remain untouched. */
    const uintptr_t stage48_pa=
#if defined(CACTUS_STAGE96_NATIVE) && CACTUS_STAGE96_NATIVE
        0x81ac042cull;
    const uint32_t stage48_expected=CACTUS96_WORD_81AC042C;
#elif defined(CACTUS_STAGE95_NATIVE) && CACTUS_STAGE95_NATIVE
        0x81ac042cull;
    const uint32_t stage48_expected=0x913a5400u;
#elif defined(CACTUS_STAGE91_NATIVE) && CACTUS_STAGE91_NATIVE
        0x81ac042cull;
    const uint32_t stage48_expected=0x913e0d29u;
#elif defined(CACTUS_STAGE90_NATIVE) && CACTUS_STAGE90_NATIVE
        0x81ac042cull;
    const uint32_t stage48_expected=0x9107dc00u;
#elif defined(CACTUS_STAGE89_NATIVE) && CACTUS_STAGE89_NATIVE
        0x81ac042cull;
    const uint32_t stage48_expected=0x97ff38d9u;
#elif defined(CACTUS_STAGE85_NATIVE) && CACTUS_STAGE85_NATIVE
        0x81ac042cull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE84_NATIVE) && CACTUS_STAGE84_NATIVE
        0x81ac01ecull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE83_NATIVE) && CACTUS_STAGE83_NATIVE
        0x81ac000cull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE82_NATIVE) && CACTUS_STAGE82_NATIVE
        0x81abfd0cull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE81_NATIVE) && CACTUS_STAGE81_NATIVE
        0x81abfb6cull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE80_NATIVE) && CACTUS_STAGE80_NATIVE
        0x81abfafcull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE79_NATIVE) && CACTUS_STAGE79_NATIVE
        0x81abebacull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
        0x81abea6cull;
    const uint32_t stage48_expected=0xf9400108u;
#elif defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
        0x81ac4488ull;
    const uint32_t stage48_expected=0x90ffb5a8u;
#elif defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
        0x81ac4368ull;
    const uint32_t stage48_expected=0x90ffb5a8u;
#elif defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
        0x81ac4348ull;
    const uint32_t stage48_expected=0x90ffb5a8u;
#elif defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
        0x81ac4028ull;
    const uint32_t stage48_expected=0x90ffb5a8u;
#elif defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
        0x81ac3ea8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
        0x81ac3e68ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
        0x81ac3e88ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
        0x81ac4028ull;
    const uint32_t stage48_expected=0x90ffb5a8u;
#elif defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
        0x81ac4068ull;
    const uint32_t stage48_expected=0x90ffb5a8u;
#elif defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
        0x81ac3e68ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
        0x81ac3d48ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
        0x81ac3bb8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
        0x81ac3998ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
        0x81ac3908ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
        0x81ac38f8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
        0x81ac37d8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
        0x81ac36f8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
        0x81ac33c8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
        0x81ac31e8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
        0x81ac3138ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
        0x81ac30d8ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
        0x81ac2f88ull;
    const uint32_t stage48_expected=0xd0ffb5a8u;
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
        0x81ac3c88ull;
    const uint32_t stage48_expected=0xb0ffb5a8u;
#else
        0x81ac0c68ull+STAGE51_EARLY_C_OFFSET;
    const uint32_t stage48_expected=0x90ffb5c8u;
#endif
    const uint32_t original=*(volatile const uint32_t *)(uintptr_t)stage48_pa;
    mark(0x4802,stage48_pa,original,(original==stage48_expected));
#endif
#if defined(CACTUS_STAGE49_FB) && CACTUS_STAGE49_FB
    /* MT6765 DTS: SMI LARB0=0x14003000. Vendor ddp_reg_pq.h:
     * NON_SEC_CON=+0x380, MMU_EN=bit0. Layer registers carry an MVA
     * when this bit is set; CPU dereference is then forbidden.
     * The Stage48 FDT proves the LK framebuffer carveout starts at
     * 0x7f0d0000 and spans 0xe20000 bytes. Require EXACTLY that
     * layout, physical-mode OVL0, and the validated pixel stride.
     * Do not alter display-controller registers or unverified IOVAs. */
    const uint32_t smi_ovl0_nonsec=stage45_reg(0x14003380ull);
    unsigned carveout=0;
    if(flags&1u) {
        for(unsigned i=0;i<display_mem.reserved_count;i++)
            if(display_mem.reserved[i].base==0x7f0d0000ull &&
               display_mem.reserved[i].size==0xe20000ull)
                carveout=1;
    }
    const unsigned physical_mode=(smi_ovl0_nonsec&1u)==0u;
    const unsigned safe=physical_mode && carveout &&
        (flags&7u)==7u && (flags&24u)==0u &&
        ovl_en==1u && ovl_src==3u &&
        l0_addr==0x7f0d0000u && (l0_pitch&0xffffu)==2944u &&
        l0_size==0x05a002d0u && l0_con==0x21ffu &&
        l1_addr==0x7f4db000u && (l1_pitch&0xffffu)==2880u &&
        l1_size==0x05a002d0u && l1_con==0x21ffu &&
        l1_off==0u;
    mark(0x4900,0x14003380ull,smi_ovl0_nonsec,physical_mode);
    mark(0x4901,safe,carveout,flags);
    if(safe) {
        /* 160x48 two-color test card on the top, full-opacity plane.
         * 30 KiB of pixels within the known reserved layer1 window.
         * D-cache clean makes MMU-off writes visible to the OVL DMA. */
        for(unsigned y=0;y<48u;y++) {
            const uintptr_t start=(uintptr_t)l1_addr+
                ((uintptr_t)(100u+y)*2880u)+80u*4u;
            volatile uint32_t *const row=(void *)start;
            const uint32_t color=y<24u ? 0xff00ff00u : 0xffff00ffu;
            for(unsigned x=0;x<160u;x++) row[x]=color;
            for(unsigned bytes=0;bytes<640u;bytes+=64u) {
                const uintptr_t cacheline=(start+bytes)&~63ull;
                __asm__ volatile("dc cvac, %0" : : "r"(cacheline) : "memory");
            }
        }
        __asm__ volatile("dsb sy" ::: "memory");
        const volatile uint32_t *const top=
            (const void *)(uintptr_t)(l1_addr+100u*2880u+80u*4u);
        const volatile uint32_t *const bottom=
            (const void *)(uintptr_t)(l1_addr+140u*2880u+80u*4u);
        const unsigned readback_ok =
            top[0]==0xff00ff00u && bottom[0]==0xffff00ffu;
        mark(0x4902,top[0],bottom[0],readback_ok);
#if defined(CACTUS_STAGE50_XNU_FB) && CACTUS_STAGE50_XNU_FB
        /* Stage49 proved that the live LK layer1 is a physically
         * reachable, FDT-reserved 720x1440x32 buffer. Give that real
         * scanout address to XNU's existing framebuffer console path.
         * Keep the old boot-args address if readback or the ABI guard
         * fails, avoiding a speculative replacement. */
        volatile struct boot_args *const xnu_args =
            (void *)(uintptr_t)loaded_boot_args_pa;
        const uint64_t old_video=xnu_args->Video.v_baseAddr;
        if(readback_ok && old_video==FB_BASE &&
           xnu_args->Video.v_rowBytes==2880u &&
           xnu_args->Video.v_width==720u &&
           xnu_args->Video.v_height==1440u &&
           xnu_args->Video.v_depth==32u) {
            xnu_args->Video.v_baseAddr=(uint64_t)l1_addr;
            const uintptr_t line=
                ((uintptr_t)&xnu_args->Video.v_baseAddr)&~(uintptr_t)63u;
            __asm__ volatile("dc cvac, %0" :: "r"(line) : "memory");
            __asm__ volatile("dsb sy" ::: "memory");
            mark(0x5000,old_video,xnu_args->Video.v_baseAddr,
                 xnu_args->Video.v_baseAddr==(uint64_t)l1_addr);
#if defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
            /* The Stage51 payload must contain the rebuilt XNU and
             * retargeted ADT. This remains a prehandoff marker: native
             * XNU execution still requires independent evidence. */
            mark(0x5100,xnu_args->Video.v_baseAddr,
                 xnu_args->deviceTreeP,xnu_args->deviceTreeLength);
#if defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
            mark(0x6100,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x15fdbdab0aa0cb1full);
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
            mark(0x6000,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x2f3b02c004763c7aull);
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
            mark(0x5900,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0xed3074cc9e889f88ull);
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
            mark(0x5800,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x9d6977d4f44b9216ull);
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
            mark(0x5700,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x7a0b778d113b3a66ull);
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
            mark(0x5600,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x3004d4478977b6b2ull);
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
            mark(0x5500,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0xea16faa6d49eb135ull);
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
            mark(0x5400,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0xed5123cee5377846ull);
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
            mark(0x5300,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x361846aab01f8040ull);
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
            /* Stage52 is a fresh kernel with persistent console marks. */
            mark(0x5200,xnu_args->Video.v_baseAddr,loaded_entry_pa,
                 0x945e61817c333218ull);
#endif
#endif
        } else {
            mark(0x50ee,old_video,xnu_args->Video.v_rowBytes,
                 ((uint64_t)xnu_args->Video.v_height<<32)|
                     xnu_args->Video.v_width);
        }
#endif
    }
#endif
#endif
}
#endif

#if defined(CACTUS_STAGE26) && CACTUS_STAGE26
/* Stage26 bridge experiment: XNU's existing early I/O L1 allocation
 * ends before VA 0xfffffff04a000000. The Stage25 hardware trace put
 * the framebuffer mapping at 0xfffffff049dbb000, only 0x245000 bytes
 * below that boundary. A 640-row window uses 0x1c2000 bytes at the
 * original 2880-byte stride, with room for 16K rounding. This changes
 * the BOOT ARGUMENT ONLY for the old XNU image. The real fix is the
 * source-level patch 0086 and requires rebuilding the XNU kernel. */
#define STAGE26_FB_HEIGHT 640u
static int stage26_restrict_fb_geometry(void)
{
    volatile struct boot_args *const ba =
        (void *)(uintptr_t)loaded_boot_args_pa;
    const uint64_t initial=ba->Video.v_height;
    if(ba->Video.v_baseAddr!=FB_BASE ||
       ba->Video.v_rowBytes!=FB_STRIDE ||
       ba->Video.v_width!=FB_W || initial!=FB_H ||
       ba->Video.v_depth!=32u ||
       STAGE26_FB_HEIGHT*FB_STRIDE>0x245000u) {
        mark(0x26ee,initial,ba->Video.v_rowBytes,ba->Video.v_baseAddr);
        return 0;
    }
    ba->Video.v_height=STAGE26_FB_HEIGHT;
    const uintptr_t field=(uintptr_t)&ba->Video.v_height;
    __asm__ volatile("dc cvac, %0; dsb sy" : : "r"(field) : "memory");
    if(ba->Video.v_height!=STAGE26_FB_HEIGHT) {
        mark(0x26ee,ba->Video.v_height,STAGE26_FB_HEIGHT,field);
        return 0;
    }
    mark(0x2600,initial,ba->Video.v_height,ba->Video.v_rowBytes);
    mark(0x2601,FB_BASE,0xfffffff049dbb000ull,0xfffffff04a000000ull);
    return 1;
}
#endif

static void store_copy(uintptr_t destination, uintptr_t source, uint64_t bytes)
{
    uint64_t n=0;
    volatile uint64_t *d=(volatile uint64_t *)destination;
    volatile const uint64_t *s=(volatile const uint64_t *)source;
    for(;n+8<=bytes;n+=8)
        d[n/8]=s[n/8];
    for(;n<bytes;n++)
        ((volatile uint8_t *)destination)[n]=
            ((volatile const uint8_t *)source)[n];
}
static void store_zero(uintptr_t destination, uint64_t bytes)
{
    uint64_t n=0;
    while(n<bytes && ((destination+n)&7u)) {
        ((volatile uint8_t *)destination)[n++]=0;
    }
    for(;n+8<=bytes;n+=8)
        *(volatile uint64_t *)(destination+n)=0;
    for(;n<bytes;n++) ((volatile uint8_t *)destination)[n]=0;
}
/* Sample copied segment endpoints and BSS; full byte-by-byte verification
 * would double the uncached boot-time traffic and can trip the watchdog. */
static int verify_copy(uintptr_t dst, uintptr_t src, uint64_t file, uint64_t vm)
{
    const uint64_t offsets[3]={0,file>32 ? file/2-16 : 0,
                                file>32 ? file-32 : 0};
    for(unsigned window=0;window<3;window++) {
        for(uint64_t i=offsets[window],end=i+32;i<end && i<file;i++)
            if(((volatile const uint8_t *)dst)[i]!=
               ((volatile const uint8_t *)src)[i]) return 0;
    }
    uint64_t tail=vm-file;
    const uint64_t zero_offsets[2]={0,tail>32 ? tail-32 : 0};
    for(unsigned window=0;window<2;window++) {
        for(uint64_t i=zero_offsets[window],end=i+32;i<end && i<tail;i++)
            if(((volatile const uint8_t *)(dst+file))[i]!=0) return 0;
    }
    return 1;
}

static unsigned perform(uintptr_t dtb)
{
    uint32_t bytes=0;
    struct fdt_info live;
    int valid=fdt_check(dtb,&bytes) && bytes<=0x100000u &&
              fdt_inspect((const void *)dtb,bytes,&live)==0;
    mark(S19_FDT,valid,valid?live.memory_count:0,valid?live.reserved_count:0);
    if(!valid) return 1;

    const struct xnu_payload *p=(const void *)(uintptr_t)PAYLOAD_ADDR;
    if((PAYLOAD_ADDR&15u) || PAYLOAD_LENGTH<XNU_PAYLOAD_HEADER_BYTES)
        return 2;
    mark(S19_PAYLOAD,p->phys_base,p->mem_size,p->nsegs);
    struct xnu_layout region;
    enum xnu_validation v=xnu_validate_payload(p,PAYLOAD_LENGTH,&live,
            dtb,bytes,(uintptr_t)_start,
            (uintptr_t)image_end-(uintptr_t)_start,&region);
    mark(S19_VALID,v,PAYLOAD_ADDR,PAYLOAD_LENGTH);
    if(v!=XNU_VALIDATE_OK) return 0x100u+(unsigned)v;
#if defined(CACTUS_STAGE20) && CACTUS_STAGE20
    loaded_entry_pa=region.entry_pa;
    loaded_boot_args_pa=region.boot_args_pa;
#endif

    mark(S19_BEFORE_COPY,region.entry_pa,region.adt_pa,
         region.boot_args_pa);
    for(uint32_t i=0;i<region.segments;i++) {
        const struct xnu_payload_segment *s=&p->segs[i];
        uintptr_t dst=(uintptr_t)(p->phys_base+
                       (s->vmaddr-p->virt_base));
        uintptr_t src=(uintptr_t)p+s->file_off;
        /* This is an EL2, MMU-off loop: all 64-bit operands aligned. */
        if((dst|src)&7u) return 0x200u+i;
        mark(S19_SEG_START,i,dst,s->file_size);
        store_copy(dst,src,s->file_size);
        store_zero(dst+s->file_size,s->vmsize-s->file_size);
        __asm__ volatile("dsb sy" ::: "memory");
        if(!verify_copy(dst,src,s->file_size,s->vmsize))
            return 0x300u+i;
        mark(S19_SEG_DONE,i,dst,s->vmsize);
        /* A bounded transmission window avoids filling the 32-slot
         * CLOG ring while copying many segments. */
        drain(40);
    }

    if((region.adt_pa|((uintptr_t)p+p->adt_off))&7u) return 0x400;
    store_copy(region.adt_pa,(uintptr_t)p+p->adt_off,p->adt_size);
    __asm__ volatile("dsb sy" ::: "memory");
    if(!verify_copy(region.adt_pa,(uintptr_t)p+p->adt_off,
                    p->adt_size,p->adt_size)) return 0x401;
    mark(S19_ADT,region.adt_pa,p->adt_size,0);
    store_zero(region.boot_args_pa,XNU_PAGE_BYTES);
    volatile struct boot_args *ba=(void *)(uintptr_t)region.boot_args_pa;
    ba->Revision=2;
    ba->Version=2;
    ba->virtBase=p->virt_base;
    ba->physBase=p->phys_base;
    ba->memSize=p->mem_size;
    ba->topOfKernelData=region.top;
    ba->Video.v_baseAddr=FB_BASE;
    ba->Video.v_display=1;
    ba->Video.v_rowBytes=FB_STRIDE;
    ba->Video.v_width=FB_W;
    ba->Video.v_height=FB_H;
    ba->Video.v_depth=32;
    ba->deviceTreeP=region.adt_pa+(p->virt_base-p->phys_base);
    ba->deviceTreeLength=(uint32_t)p->adt_size;
    for(unsigned i=0;i<608u;i++) ba->CommandLine[i]=p->cmdline[i];
    ba->CommandLine[607]=0;
    ba->bootFlags=0;
    ba->memSizeActual=p->mem_size;
    __asm__ volatile("dsb sy" ::: "memory");
    if(ba->Revision!=2 || ba->physBase!=p->phys_base ||
       ba->deviceTreeLength!=p->adt_size) return 0x402;
    mark(S19_BOOTARGS,region.boot_args_pa,ba->deviceTreeP,region.top);
    /* Flush instructions for future XNU entry, but Stage19-A itself
     * runs no XNU code and keeps Linux recovery as fallback. */
    __asm__ volatile("ic iallu; dsb sy; isb" ::: "memory");
    mark(S19_COPY_DONE,region.entry_pa,region.boot_args_pa,region.top);
    return 0;
}

void stage19_probe(uintptr_t dtb)
{
    uint64_t el;
#if defined(CACTUS_STAGE38_WDT) && CACTUS_STAGE38_WDT
    /* This entry comes from a chainloader, which cannot assume that
     * C .bss is zero. Do not accidentally reload the watchdog before
     * explicitly reading its current MODE register. */
    stage38_wdt_enabled=0;
    stage38_last_reload=0;
#endif
    __asm__ volatile("mrs %0, CurrentEL":"=r"(el));
    __asm__ volatile("mrs %0, cntfrq_el0":"=r"(frequency));
    if(!frequency) frequency=13000000u;
    online=faulted=heartbeat_count=0;
#if defined(CACTUS_STAGE20) && CACTUS_STAGE20
    cactus_trace_reset(0xca200001u);
#else
    cactus_trace_reset(0xca190001u);
#endif
    mark(S19_ENTRY,dtb,el,frequency);
    online=usb_init(usb_diag);
    mark(S19_USB,online,usb_diag[1],usb_diag[2]);
    if(!online) return;
#if defined(CACTUS_STAGE88_MSDC_READ) && CACTUS_STAGE88_MSDC_READ
    cactus88_probe_emmc();
#endif
#if defined(CACTUS_STAGE62_GICR_MMIO) && CACTUS_STAGE62_GICR_MMIO
    stage62_gicr_physical_census();
#endif
#if defined(CACTUS_STAGE39_WDT_HANDOFF) && CACTUS_STAGE39_WDT_HANDOFF
    /* Keep any inherited RGU watchdog alive while loading the Mach-O
     * and waiting for COM25; XNU itself cannot service it yet. */
    stage38_sample(0x3901);
#endif
    unsigned status=perform(dtb);
#if defined(CACTUS_STAGE20) && CACTUS_STAGE20
    if(status==0) {
#if defined(CACTUS_STAGE20B) && CACTUS_STAGE20B
        if(!stage20b_arm()) {
            status=0x510;
        } else {
#endif
        mark(0x20a0,loaded_entry_pa,loaded_boot_args_pa,8u);
#if defined(CACTUS_STAGE22) && CACTUS_STAGE22
        /* Read-only EL2 CPU/timer census and the actual loaded boot_args.
         * No speculative GIC accesses or timer programming. */
        uint64_t midr, mpidr, cntfrq, cntpct, cntvct;
        __asm__ volatile("mrs %0, MIDR_EL1" : "=r"(midr));
        __asm__ volatile("mrs %0, MPIDR_EL1" : "=r"(mpidr));
        __asm__ volatile("mrs %0, CNTFRQ_EL0" : "=r"(cntfrq));
        __asm__ volatile("mrs %0, CNTPCT_EL0" : "=r"(cntpct));
        __asm__ volatile("mrs %0, CNTVCT_EL0" : "=r"(cntvct));
        const volatile struct boot_args *const ba=
            (const void *)(uintptr_t)loaded_boot_args_pa;
        mark(0x2200,midr,mpidr,8u);
        mark(0x2201,cntfrq,cntpct,cntvct);
        mark(0x2202,ba->physBase,ba->memSize,ba->topOfKernelData);
        mark(0x2205,STAGE20B_TARGET,STAGE22_TARGET_VA,usb_diag[8]);
#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
        /* Keep a visible color sample on the MI splash for the full
         * COM25 preflight enumeration interval. */
#if defined(CACTUS_STAGE45_COMBINED) && CACTUS_STAGE45_COMBINED
        stage45_scanout_probe(dtb);
        {
#else
        if(!stage23_splash_probe()) {
            status=0x523;
            (void)stage20b_restore();
        } else {
#endif
#endif
        drain(5500);
#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
        }
#endif
#elif defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
        mark(0x21ea,STAGE20B_TARGET,STAGE21D_TARGET_VA,usb_diag[8]);
        drain(5500);
#elif defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
        mark(0x21da,STAGE20B_TARGET,STAGE21C2_VBAR_VA,usb_diag[8]);
        drain(5500);
#elif defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
        /* Allow Windows to enumerate CDC and receive the pre-XNU markers
         * even if the later EL1t page-table path never reaches the HVC. */
        mark(0x21ca,STAGE20B_TARGET,STAGE20D_SYNC_SLOT,usb_diag[8]);
        drain(5500);
#endif
        /* ERET enters shim EL1; Stage20-B/C then branch to real XNU. */
#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
        if(status==0) {
#if defined(CACTUS_STAGE26) && CACTUS_STAGE26
            if(!stage26_restrict_fb_geometry()) {
                status=0x526;
            } else {
#endif
            mark(0x2303,loaded_entry_pa,loaded_boot_args_pa,
                 STAGE22_TARGET_VA);
#if defined(CACTUS_STAGE28_FIX) && CACTUS_STAGE28_FIX
#if defined(CACTUS_STAGE96_NATIVE) && CACTUS_STAGE96_NATIVE
            mark(0x2800,CACTUS96_KERNEL_PREFIX,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE95_NATIVE) && CACTUS_STAGE95_NATIVE
            mark(0x2800,0x66d7e63cfd396c2cull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE91_NATIVE) && CACTUS_STAGE91_NATIVE
            mark(0x2800,0xb22e157d0eedc234ull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE90_NATIVE) && CACTUS_STAGE90_NATIVE
            mark(0x2800,0x376706e72c2f15ebull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE89_NATIVE) && CACTUS_STAGE89_NATIVE
            mark(0x2800,0x3fa61a4f8a246abbull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE85_NATIVE) && CACTUS_STAGE85_NATIVE
            mark(0x2800,0xdd39a64cd43de54dull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE84_NATIVE) && CACTUS_STAGE84_NATIVE
            mark(0x2800,0xdae21a356c72c79full,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE83_NATIVE) && CACTUS_STAGE83_NATIVE
            mark(0x2800,0xf3cf4c7978388b30ull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE82_NATIVE) && CACTUS_STAGE82_NATIVE
            mark(0x2800,0xdb8fa92517586342ull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE81_NATIVE) && CACTUS_STAGE81_NATIVE
            mark(0x2800,0xc38d4ebda19c6693ull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE80_NATIVE) && CACTUS_STAGE80_NATIVE
            mark(0x2800,0xaf41e570707774fbull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE79_NATIVE) && CACTUS_STAGE79_NATIVE
            mark(0x2800,0x32212e13ff1a92e3ull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE78_NATIVE) && CACTUS_STAGE78_NATIVE
            mark(0x2800,0x1779340d044523adull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE77_NATIVE) && CACTUS_STAGE77_NATIVE
            mark(0x2800,0x60d31b08a485278cull,loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE76_NATIVE) && CACTUS_STAGE76_NATIVE
            mark(0x2800,0x7316640649e655d6ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE75_NATIVE) && CACTUS_STAGE75_NATIVE
            mark(0x2800,0xfd4d640bc716f1a7ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE74_NATIVE) && CACTUS_STAGE74_NATIVE
            mark(0x2800,0x611fc800acd2b829ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE73_NATIVE) && CACTUS_STAGE73_NATIVE
            mark(0x2800,0xd5063f7f09bb5a51ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE72_NATIVE) && CACTUS_STAGE72_NATIVE
            mark(0x2800,0x3b1ae5e7f1ba8c76ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE71_NATIVE) && CACTUS_STAGE71_NATIVE
            mark(0x2800,0xead2ac800bac9452ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE70_NATIVE) && CACTUS_STAGE70_NATIVE
            mark(0x2800,0xc9645c067882397dull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE69_NATIVE) && CACTUS_STAGE69_NATIVE
            mark(0x2800,0xc2a15e3bcca44e1aull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE68_NATIVE) && CACTUS_STAGE68_NATIVE
            mark(0x2800,0xdf201510edfda5e2ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE67_NATIVE) && CACTUS_STAGE67_NATIVE
            mark(0x2800,0x5fde9842617a904dull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE66_NATIVE) && CACTUS_STAGE66_NATIVE
            mark(0x2800,0x9f76552002e5ba8full,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE65_NATIVE) && CACTUS_STAGE65_NATIVE
            mark(0x2800,0x8b9d47e456c92f59ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE63_NATIVE) && CACTUS_STAGE63_NATIVE
            mark(0x2800,0xc9b059c9dad73f49ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE61_GICR_ID) && CACTUS_STAGE61_GICR_ID
            mark(0x2800,0x15fdbdab0aa0cb1full,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE60_GICR) && CACTUS_STAGE60_GICR
            mark(0x2800,0x2f3b02c004763c7aull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE59_IRQ_WAIT) && CACTUS_STAGE59_IRQ_WAIT
            mark(0x2800,0xed3074cc9e889f88ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE58_GICV3_REARM) && CACTUS_STAGE58_GICV3_REARM
            mark(0x2800,0x9d6977d4f44b9216ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE57_CPU0_IRQ) && CACTUS_STAGE57_CPU0_IRQ
            mark(0x2800,0x7a0b778d113b3a66ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE56_CPU_SYNC) && CACTUS_STAGE56_CPU_SYNC
            mark(0x2800,0x3004d4478977b6b2ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE55_BSD_GATE) && CACTUS_STAGE55_BSD_GATE
            mark(0x2800,0xea16faa6d49eb135ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE54_IOKIT_BSD) && CACTUS_STAGE54_IOKIT_BSD
            mark(0x2800,0xed5123cee5377846ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE53_LIVE_CONSOLE) && CACTUS_STAGE53_LIVE_CONSOLE
            mark(0x2800,0x361846aab01f8040ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE52_LIVE_CONSOLE) && CACTUS_STAGE52_LIVE_CONSOLE
            mark(0x2800,0x945e61817c333218ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#elif defined(CACTUS_STAGE51_LIVE_CONSOLE) && CACTUS_STAGE51_LIVE_CONSOLE
            /* New Cactus XNU from Actions run 40099595534: SHA256
             * 40f672d3500699b6ee8655e9e33e0ab29e7b410104e01618598bb9ea17d5921a. */
            mark(0x2800,0x40f672d3500699b6ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#else
            /* GitHub Actions run 40003701253, CACTUS XNU patches 0086
             * and 0087; a build provenance marker only. */
            mark(0x2800,0x1a0cf300cd5a6f86ull,
                 loaded_entry_pa,loaded_boot_args_pa);
#endif
#elif defined(CACTUS_STAGE27) && CACTUS_STAGE27
            /* Exact GitHub Actions run 39995786681 XNU Mach-O SHA256
             * a1b8677a3449664fd17a9ee4b3740a76d2d489d0dbf1dce5e4ca5887f3840008.
             * This marker establishes which kernel build was embedded,
             * not proof of execution past the old framebuffer panic. */
            mark(0x2700,0xa1b8677a3449664full,
                 loaded_entry_pa,loaded_boot_args_pa);
#endif
#if defined(CACTUS_STAGE38_WDT) && CACTUS_STAGE38_WDT
            /* Snapshot inherited RGU state before XNU. This is read-only;
             * reloads begin only if the EL1 exception returns to EL2. */
            mark(0x3802,stage38_rgu_read(0),stage38_rgu_read(4),
                 stage38_rgu_read(12));
#endif
#if defined(CACTUS_STAGE35) && CACTUS_STAGE35
            /* Host delivery is possible only while the shim still owns
             * physical MUSB. 0x2303/0x2800 mean transition is imminent,
             * not that XNU executed. 0x20a1 proves native EL1 entry. */
            mark(0x3500,loaded_entry_pa,loaded_boot_args_pa,
                 cactus_trace_pending());
            drain(850);
            if(cactus_trace_pending()) {
                mark(0x35ee,cactus_trace_pending(),
                     cactus_trace_dropped(),usb_diag[8]);
                /* No silent handoff when pre-EL1 diagnostics could not
                 * be sent. Preserve USB for a delayed host connection. */
                for(;;) drain(1000);
            }
#endif
#if defined(CACTUS_STAGE39_WDT_HANDOFF) && CACTUS_STAGE39_WDT_HANDOFF
            if(!stage39_disarm_before_xnu()) {
                mark(0x39ee,stage38_rgu_read(0),
                     stage38_rgu_read(4),0x539);
                /* A failed WDT disable is observable on COM25. Do not
                 * proceed into XNU with a known armed reset timer. */
                for(;;) drain(1000);
            }
            drain(850);
            if(cactus_trace_pending()) {
                mark(0x39ef,cactus_trace_pending(),
                     cactus_trace_dropped(),usb_diag[8]);
                for(;;) drain(1000);
            }
#endif
            stage20_el1_transition(loaded_entry_pa,loaded_boot_args_pa);
#if defined(CACTUS_STAGE26) && CACTUS_STAGE26
            }
#endif
        }
#else
        stage20_el1_transition(loaded_entry_pa,loaded_boot_args_pa);
#endif
        uint64_t now_el;
        __asm__ volatile("mrs %0, CurrentEL":"=r"(now_el));
        mark(0x20a3,now_el,loaded_entry_pa,loaded_boot_args_pa);
        if(now_el!=8u) status=0x500;
#if defined(CACTUS_STAGE20B) && CACTUS_STAGE20B
#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
        if(status!=0x523 && !stage20b_restore()) status=0x511;
#else
        if(!stage20b_restore()) status=0x511;
#endif
#if defined(CACTUS_STAGE23) && CACTUS_STAGE23
        if(status!=0x523) {
            /* A genuine synchronous exception has returned control to
             * EL2. Keep the COM25 endpoint polled and the fault readable;
             * never intentionally restart the boot/recovery chain. */
            mark(0x2308,status,stage20b_trap_ok,stage20b_hvc_ok);
            mark(0x20ff,status,cactus_trace_pending(),cactus_trace_dropped());
            mark(S19_DONE,status,cactus_trace_pending(),cactus_trace_dropped());
            for(;;) drain(1000);
        }
#endif
        }
#endif
    }
    mark(0x20ff,status,cactus_trace_pending(),cactus_trace_dropped());
#endif
    mark(S19_DONE,status,cactus_trace_pending(),cactus_trace_dropped());
    drain(5500);
    usb_shutdown();
    online=0;
}
#if defined(CACTUS_STAGE20) && CACTUS_STAGE20
/* Executed with MMU off at the new privilege level before HVC. The CLOG
 * frame's own CurrentEL field also independently reports EL1. */
void stage20_el1_signal(uint64_t entry,uint64_t boot_args)
{
    uint64_t el;
    __asm__ volatile("mrs %0, CurrentEL":"=r"(el));
    mark(0x20a1,el,entry,boot_args);
}
void stage20_hvc_signal(uint64_t esr,uint64_t elr,uint64_t spsr)
{
    mark(0x20a2,esr,elr,spsr);
}
#if defined(CACTUS_STAGE20B) && CACTUS_STAGE20B
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
void stage20b_el1_exception(uint64_t esr,uint64_t elr,uint64_t far,
                           uint64_t saved_bootargs,
                           uint64_t virtbase,uint64_t physbase,
                           uint64_t memsize,uint64_t vbar)
#else
void stage20b_el1_exception(uint64_t esr,uint64_t elr,uint64_t far,
                           uint64_t saved_bootargs)
#endif
{
    stage20b_trap_ok=((esr>>26)==0x3cu &&
                      (esr&0xffffu)==STAGE20B_IMM &&
                      elr==STAGE20B_TARGET);
    mark(STAGE20B_TRAP_EVENT,esr,elr,far);
#if defined(CACTUS_STAGE20D) && CACTUS_STAGE20D
    const volatile struct boot_args *const ba=
        (const void *)(uintptr_t)loaded_boot_args_pa;
    mark(0x20d2,vbar,saved_bootargs,virtbase);
    mark(0x20d3,physbase,memsize,ba->memSize);
    stage20b_trap_ok=stage20b_trap_ok &&
        vbar==STAGE20D_VECTOR_BASE &&
        saved_bootargs==loaded_boot_args_pa &&
        virtbase==ba->virtBase &&
        physbase==ba->physBase &&
        memsize==ba->memSize;
#endif
#if defined(CACTUS_STAGE20C) && CACTUS_STAGE20C
    uint64_t first=0,last=0;
    if(stage20b_trap_ok) {
        first=*(volatile const uint32_t *)(uintptr_t)STAGE20C_FB_FIRST;
        last=*(volatile const uint32_t *)(uintptr_t)STAGE20C_FB_LAST;
    }
    mark(0x20c2,saved_bootargs,first,last);
    stage20b_trap_ok = stage20b_trap_ok &&
                      saved_bootargs==loaded_boot_args_pa &&
                      first==0xffffffffull && last==0xffffffffull;
#else
    (void)saved_bootargs;
#endif
}
#if defined(CACTUS_STAGE24) && CACTUS_STAGE24
/* Strict 4K, 39-bit TTBR1 page walk using the EL2 physical identity map.
 * Every table and resulting address must stay in the measured cactus
 * loader RAM window. This protects COM25 capture from wild XNU stack VAs.
 * XNU may legitimately use other mappings; in that case simply log no
 * frame, rather than touching unknown physical RAM or MMIO. */
static int stage24_in_ram(uint64_t pa,uint64_t size)
{
    return pa>=0x80000000ull && size<=0x1e000000ull &&
           pa<=0x9e000000ull-size;
}
static int stage24_translate(uint64_t va,uint64_t root,uint64_t *pa_out)
{
    const uint64_t pa_mask=0x0000fffffffff000ull;
    if((va>>39)!=0x1ffffffull || (root&0xfffull)) return 0;
    uint64_t table=root&pa_mask;
    for(unsigned level=0;level<3;level++) {
        const unsigned shift=30u-9u*level;
        const uint64_t slot=table+8u*((va>>shift)&0x1ffull);
        if(!stage24_in_ram(slot,8)) return 0;
        const uint64_t desc=*(volatile const uint64_t *)(uintptr_t)slot;
        const uint64_t kind=desc&3ull;
        if(kind==3u && level!=2u) {
            table=desc&pa_mask;
            if(!stage24_in_ram(table,4096)) return 0;
        } else if((kind==1u && level!=2u) ||
                  (kind==3u && level==2u)) {
            const uint64_t offset=(1ull<<shift)-1ull;
            const uint64_t pa=((desc&pa_mask)&~offset)|(va&offset);
            if(!stage24_in_ram(pa,8)) return 0;
            *pa_out=pa;
            return 1;
        } else return 0;
    }
    return 0;
}
/* The active cactus intstack is in the loaded XNU __BOOTDATA segment.
 * Early XNU image VAs are loaded contiguously at physBase + (VA-virtBase).
 * The exact __BOOTDATA bounds are verified by the Stage22 Mach-O payload
 * guard. This second bounded lookup does not depend on XNU TTBR1: it is
 * needed while pmap init is itself panicking on a missing page-table PTE. */
static int stage24_bootdata_pa(uint64_t va,uint64_t *pa_out)
{
    const uint64_t base=0xfffffff008068000ull;
    const uint64_t end=0xfffffff0080b4000ull;
    if(va<base || va>end-8u) return 0;
    const uint64_t pa=0x80000000ull+(va-0xfffffff006000000ull);
    if(!stage24_in_ram(pa,8)) return 0;
    *pa_out=pa;
    return 1;
}
static void stage24_log_callers(uint64_t tcr,uint64_t ttbr1,uint64_t fp)
{
    /* T1SZ=25 and TG1=4KB required by this three-level walker. */
    const int walker_ok=(((tcr>>16)&0x3fu)==25u &&
       ((tcr>>30)&3u)==2u &&
       stage24_in_ram(ttbr1&0x0000fffffffff000ull,4096));
    unsigned frames=0;
    for(;frames<4;frames++) {
        uint64_t frame_pa=0,return_pa=0;
        if(fp&15u) break;
        const int walked=(walker_ok &&
            stage24_translate(fp,ttbr1,&frame_pa) &&
            stage24_translate(fp+8u,ttbr1,&return_pa));
        if(!walked && !(stage24_bootdata_pa(fp,&frame_pa) &&
                        stage24_bootdata_pa(fp+8u,&return_pa))) break;
        mark(0x241e,fp,frame_pa,(uint64_t)(walked ? 1u : 2u));
        const uint64_t prev=*(volatile const uint64_t *)(uintptr_t)frame_pa;
        const uint64_t lr=*(volatile const uint64_t *)(uintptr_t)return_pa;
        mark(0x2410u+frames,fp,prev,lr);
        if(prev<=fp || prev-fp>0x10000u) {frames++;break;}
        fp=prev;
    }
    mark(0x241f,fp,ttbr1,frames);
}
#endif
#if defined(CACTUS_STAGE25) && CACTUS_STAGE25
/* Read the actual XNU TTBR1 descriptors for the failing VA. Inspection
 * only: no mapping is made until the required PA/VA interval is known. */
static void stage25_log_missing_pte(uint64_t va,uint64_t ttbr1)
{
    const uint64_t mask=0x0000fffffffff000ull;
    uint64_t table=ttbr1&mask;
    unsigned visited=0;
    for(unsigned level=0;level<3u;level++) {
        const unsigned shift=30u-9u*level;
        const uint64_t slot=table + 8u*((va>>shift)&0x1ffull);
        if(!stage24_in_ram(slot,8u)) break;
        const uint64_t desc=*(volatile const uint64_t *)(uintptr_t)slot;
        mark(0x2504u+level,slot,desc,(uint64_t)level);
        visited++;
        if(level==2u || (desc&3u)!=3u) break;
        table=desc&mask;
        if(!stage24_in_ram(table,4096u)) break;
    }
    mark(0x2507,va,ttbr1,visited);
}
#endif
void stage20b_hvc_exception(uint64_t esr,uint64_t elr,uint64_t spsr)
{
#if defined(CACTUS_STAGE38_WDT) && CACTUS_STAGE38_WDT
    /* The BRK/HVC handshake has returned to the EL2 diagnostic stack;
     * XNU no longer owns this CPU. Enable conditional servicing only
     * for the captured-fault hold, leaving watchdog config intact. */
    stage38_sample(0x3800);
#endif
#if defined(CACTUS_STAGE22) && CACTUS_STAGE22
    /* Observe the first synchronous exception or the late C join using
     * the proven virtual EL1t/EL1h HVC stubs and the EL2 physical stack. */
    uint64_t esr1,elr1,far1,vbar,tcr,ttbr0,ttbr1,mair,sctlr,spsr1;
    __asm__ volatile("mrs %0, ESR_EL1":"=r"(esr1));
    __asm__ volatile("mrs %0, ELR_EL1":"=r"(elr1));
    __asm__ volatile("mrs %0, FAR_EL1":"=r"(far1));
    __asm__ volatile("mrs %0, VBAR_EL1":"=r"(vbar));
    __asm__ volatile("mrs %0, TCR_EL1":"=r"(tcr));
    __asm__ volatile("mrs %0, TTBR0_EL1":"=r"(ttbr0));
    __asm__ volatile("mrs %0, TTBR1_EL1":"=r"(ttbr1));
    __asm__ volatile("mrs %0, MAIR_EL1":"=r"(mair));
    __asm__ volatile("mrs %0, SCTLR_EL1":"=r"(sctlr));
    __asm__ volatile("mrs %0, SPSR_EL1":"=r"(spsr1));
    const unsigned ec=(unsigned)(esr1>>26);
    const unsigned checkpoint=(ec==0x3cu &&
        (esr1&0xffffu)==STAGE20B_IMM && elr1==STAGE22_TARGET_VA);
    /* kind: 1=post-init calls checkpoint, 2=exception, 3=other BRK. */
    const unsigned kind=checkpoint ? 1u : ((ec==0x3cu) ? 3u : 2u);
    mark(STAGE20B_TRAP_EVENT,esr1,elr1,far1);
#if defined(CACTUS_STAGE24) && CACTUS_STAGE24
    /* The HVC vector runs with EL2 MMU disabled. Snapshot original XNU
     * registers in assembly before any C function or ABI clobber. We
     * only read the known physical shim buffer; NEVER dereference an
     * untrusted high-VA frame pointer or panic string here. */
    extern uint64_t stage24_register_snapshot[23];
    const volatile uint64_t *const r=stage24_register_snapshot;
    mark(0x2400,r[19],r[20],r[22]); /* x29, LR/x30, SP_EL1 */
    mark(0x2401,r[0],r[1],r[2]);    /* x0..x2 */
    mark(0x2402,r[3],r[4],r[5]);    /* x3..x5 */
    mark(0x2403,r[6],r[7],r[8]);    /* x6..x8 */
    mark(0x2404,r[9],r[10],r[11]); /* x19..x21 */
    mark(0x2405,r[12],r[13],r[14]);/* x22..x24 */
    mark(0x2406,r[15],r[16],r[17]);/* x25..x27 */
#if defined(CACTUS_STAGE45_COMBINED) && CACTUS_STAGE45_COMBINED
    mark(0x2407,r[18],r[21],CACTUS_TRACE_STAGE);
#elif defined(CACTUS_STAGE44_NEXT_RETURN) && CACTUS_STAGE44_NEXT_RETURN
    mark(0x2407,r[18],r[21],44u);
#elif defined(CACTUS_STAGE43_NEXT_INIT) && CACTUS_STAGE43_NEXT_INIT
    mark(0x2407,r[18],r[21],43u);
#elif defined(CACTUS_STAGE42_AFTER_CALLEE) && CACTUS_STAGE42_AFTER_CALLEE
    mark(0x2407,r[18],r[21],42u);
#elif defined(CACTUS_STAGE41_CALLEE_ENTRY) && CACTUS_STAGE41_CALLEE_ENTRY
    mark(0x2407,r[18],r[21],41u);
#elif defined(CACTUS_STAGE40_LATE_C) && CACTUS_STAGE40_LATE_C
    mark(0x2407,r[18],r[21],40u);
#elif defined(CACTUS_STAGE39_WDT_HANDOFF) && CACTUS_STAGE39_WDT_HANDOFF
    mark(0x2407,r[18],r[21],39u);
#elif defined(CACTUS_STAGE38_WDT) && CACTUS_STAGE38_WDT
    mark(0x2407,r[18],r[21],38u);
#elif defined(CACTUS_STAGE37_PMAP) && CACTUS_STAGE37_PMAP
    mark(0x2407,r[18],r[21],37u);
#elif defined(CACTUS_STAGE36_CHECKPOINT) && CACTUS_STAGE36_CHECKPOINT
    mark(0x2407,r[18],r[21],36u);
#elif defined(CACTUS_STAGE35) && CACTUS_STAGE35
    mark(0x2407,r[18],r[21],35u);  /* x28, SP_EL0, Stage35 */
#elif defined(CACTUS_STAGE28_FIX) && CACTUS_STAGE28_FIX
    mark(0x2407,r[18],r[21],34u);  /* x28, SP_EL0, full XNU Stage34 */
#elif defined(CACTUS_STAGE28) && CACTUS_STAGE28
    mark(0x2407,r[18],r[21],33u);  /* x28, SP_EL0, rebuilt Stage33 PTE probe */
#elif defined(CACTUS_STAGE27) && CACTUS_STAGE27
    mark(0x2407,r[18],r[21],32u);  /* x28, SP_EL0, rebuilt XNU Stage32 */
#elif defined(CACTUS_STAGE26) && CACTUS_STAGE26
    mark(0x2407,r[18],r[21],31u);  /* x28, SP_EL0, Stage31 */
#elif defined(CACTUS_STAGE25) && CACTUS_STAGE25
    mark(0x2407,r[18],r[21],30u);  /* x28, SP_EL0, Stage30 */
#else
    mark(0x2407,r[18],r[21],0x29u);/* x28, SP_EL0, old build ID */
#endif
#if defined(CACTUS_STAGE25) && CACTUS_STAGE25
    const unsigned pmap_hit=(esr1==0xf2000e25ull &&
                             elr1==STAGE25_PMAP_VA);
    mark(0x2501,esr1,elr1,pmap_hit);
    if(pmap_hit) {
        /* x19=current VA, x20=initial VA, x21=end PA, x22=start PA.
         * These are saved callee-saved regs inside pmap_map_bd itself. */
        mark(0x2502,r[9],r[12],r[11]);
        mark(0x2503,r[10],r[13],r[14]);
        stage25_log_missing_pte(r[9],ttbr1);
    }
#endif
    stage24_log_callers(tcr,ttbr1,r[19]);
#endif
    mark(0x2207,vbar,tcr,sctlr);
    mark(0x2208,ttbr0,ttbr1,mair);
    mark(0x2209,elr,spsr,spsr1);
    mark(0x220a,kind,elr1,ec);
    stage20b_trap_ok=(vbar==STAGE21C2_VBAR_VA &&
        (sctlr&1u)!=0u &&
        ((spsr1&0xfu)==4u || (spsr1&0xfu)==5u) &&
        (elr==STAGE21C2_VBAR_VA+4ull ||
         elr==STAGE21C2_VBAR_VA+0x204ull));
    const unsigned expected_el_mode=5u;
#elif defined(CACTUS_STAGE21D) && CACTUS_STAGE21D
    /* Both virtual synchronous exception slots contain an HVC-only
     * trampoline. The logger uses EL2's physical stack and mappings. */
    uint64_t esr1,elr1,far1,vbar,tcr,ttbr0,ttbr1,mair,sctlr,spsr1;
    __asm__ volatile("mrs %0, ESR_EL1":"=r"(esr1));
    __asm__ volatile("mrs %0, ELR_EL1":"=r"(elr1));
    __asm__ volatile("mrs %0, FAR_EL1":"=r"(far1));
    __asm__ volatile("mrs %0, VBAR_EL1":"=r"(vbar));
    __asm__ volatile("mrs %0, TCR_EL1":"=r"(tcr));
    __asm__ volatile("mrs %0, TTBR0_EL1":"=r"(ttbr0));
    __asm__ volatile("mrs %0, TTBR1_EL1":"=r"(ttbr1));
    __asm__ volatile("mrs %0, MAIR_EL1":"=r"(mair));
    __asm__ volatile("mrs %0, SCTLR_EL1":"=r"(sctlr));
    __asm__ volatile("mrs %0, SPSR_EL1":"=r"(spsr1));
    mark(STAGE20B_TRAP_EVENT,esr1,elr1,far1);
    mark(0x21e2,vbar,tcr,sctlr);
    mark(0x21e3,ttbr0,ttbr1,mair);
    mark(0x21e4,elr,spsr,spsr1);
    const unsigned ec=(unsigned)(esr1>>26);
    const unsigned checkpoint=(ec==0x3cu &&
                               (esr1&0xffffu)==STAGE20B_IMM &&
                               elr1==STAGE21D_TARGET_VA);
    /* Any earlier non-BRK exception is a separately classified fault. */
    const unsigned fault=ec!=0x3cu;
    const unsigned kind=checkpoint ? 1u : (fault ? 2u : 0u);
    mark(0x21e5,kind,elr1,(uint64_t)ec);
    stage20b_trap_ok=(kind!=0u &&
                      vbar==STAGE21C2_VBAR_VA &&
                      tcr==0x22a5192519ull &&
                      ttbr0==0x8117a000ull &&
                      ttbr1==0x8117b000ull &&
                      mair==0x0c08044f00bb44ffull &&
                      (sctlr&1u)!=0u &&
                      ((spsr1&0xfu)==4u || (spsr1&0xfu)==5u) &&
                      (elr==STAGE21C2_VBAR_VA+4ull ||
                       elr==STAGE21C2_VBAR_VA+0x204ull));
    const unsigned expected_el_mode=5u;
#elif defined(CACTUS_STAGE21C2) && CACTUS_STAGE21C2
    /* EL1 has just enabled translations. HVC enters the still-MMU-off
     * EL2 logger using its own physical stack and data addresses. */
    uint64_t esr1,elr1,far1,vbar,tcr,ttbr0,ttbr1,mair,sctlr,spsr1;
    __asm__ volatile("mrs %0, ESR_EL1":"=r"(esr1));
    __asm__ volatile("mrs %0, ELR_EL1":"=r"(elr1));
    __asm__ volatile("mrs %0, FAR_EL1":"=r"(far1));
    __asm__ volatile("mrs %0, VBAR_EL1":"=r"(vbar));
    __asm__ volatile("mrs %0, TCR_EL1":"=r"(tcr));
    __asm__ volatile("mrs %0, TTBR0_EL1":"=r"(ttbr0));
    __asm__ volatile("mrs %0, TTBR1_EL1":"=r"(ttbr1));
    __asm__ volatile("mrs %0, MAIR_EL1":"=r"(mair));
    __asm__ volatile("mrs %0, SCTLR_EL1":"=r"(sctlr));
    __asm__ volatile("mrs %0, SPSR_EL1":"=r"(spsr1));
    mark(STAGE20B_TRAP_EVENT,esr1,elr1,far1);
    mark(0x21d2,vbar,tcr,sctlr);
    mark(0x21d3,ttbr0,ttbr1,mair);
    const volatile uint64_t *const root0=(const void *)0x8117a000ull;
    const volatile uint64_t *const root1=(const void *)0x8117b000ull;
    const volatile uint64_t *const phys=(const void *)0x8117c000ull;
    const volatile uint64_t *const high=(const void *)0x8117d000ull;
    const uint64_t r0=root0[2],r1=root1[0x1c0];
    const uint64_t p8=phys[8],h38=high[0x38];
    mark(0x21d4,r0,r1,p8);
    mark(0x21d8,h38,root1[0x180],phys[0xee]);
    mark(0x21d5,elr,spsr,spsr1);
    stage20b_trap_ok=((esr1>>26)==0x3cu &&
                      (esr1&0xffffu)==STAGE20B_IMM &&
                      elr1==STAGE20B_TARGET &&
                      vbar==STAGE21C2_VBAR_VA &&
                      tcr==0x22a5192519ull &&
                      ttbr0==0x8117a000ull &&
                      ttbr1==0x8117b000ull &&
                      mair==0x0c08044f00bb44ffull &&
                      /* Cortex-A53 readback adds bit 23 to XNU's
                       * 0x3454593d SCTLR write (observed on hardware
                       * in three independent Stage25 COM captures). */
                      sctlr==0x34d4593dull &&
                      r0==0x8117c003ull &&
                      r1==0x8117d003ull &&
                      p8==0x81000601ull &&
                      h38==0x81000601ull &&
                      elr==STAGE21C2_VBAR_VA+4ull &&
                      (spsr1&0xfu)==4u);
    const unsigned expected_el_mode=5u;
#elif defined(CACTUS_STAGE21C1) && CACTUS_STAGE21C1
    /* HVC runs on the known-good EL2 physical stack. Reading EL1 state
     * here avoids both virtual XNU stack pointers while its MMU is OFF. */
    uint64_t esr1,elr1,far1,vbar,tcr,ttbr0,ttbr1,mair,sctlr,spsr1;
    __asm__ volatile("mrs %0, ESR_EL1":"=r"(esr1));
    __asm__ volatile("mrs %0, ELR_EL1":"=r"(elr1));
    __asm__ volatile("mrs %0, FAR_EL1":"=r"(far1));
    __asm__ volatile("mrs %0, VBAR_EL1":"=r"(vbar));
    __asm__ volatile("mrs %0, TCR_EL1":"=r"(tcr));
    __asm__ volatile("mrs %0, TTBR0_EL1":"=r"(ttbr0));
    __asm__ volatile("mrs %0, TTBR1_EL1":"=r"(ttbr1));
    __asm__ volatile("mrs %0, MAIR_EL1":"=r"(mair));
    __asm__ volatile("mrs %0, SCTLR_EL1":"=r"(sctlr));
    __asm__ volatile("mrs %0, SPSR_EL1":"=r"(spsr1));
    mark(STAGE20B_TRAP_EVENT,esr1,elr1,far1);
    mark(0x21c2,vbar,tcr,sctlr);
    mark(0x21c3,ttbr0,ttbr1,mair);
    const volatile uint64_t *const root0=(const void *)0x8117a000ull;
    const volatile uint64_t *const root1=(const void *)0x8117b000ull;
    const volatile uint64_t *const phys=(const void *)0x8117c000ull;
    const volatile uint64_t *const high=(const void *)0x8117d000ull;
    const volatile uint64_t *const fb=(const void *)0x8117e000ull;
    const uint64_t r0=root0[2],r1=root1[0x1c0],rf=root1[0x180];
    const uint64_t p8=phys[8],h38=high[0x38],f1=fb[1];
    const uint64_t f2=fb[2],tail=phys[0xef],last=phys[0xee];
    mark(0x21c4,r0,r1,rf);
    mark(0x21c7,p8,h38,f1);
    mark(0x21c8,f2,tail,last);
    /* EL1t BRK enters the EL1h vector, so its HVC saves EL1h in
     * SPSR_EL2. SPSR_EL1 independently retains the original EL1t. */
    mark(0x21c9,elr,spsr,spsr1);
    stage20b_trap_ok=((esr1>>26)==0x3cu &&
                      (esr1&0xffffu)==STAGE20B_IMM &&
                      elr1==STAGE20B_TARGET &&
                      vbar==STAGE20D_VECTOR_BASE &&
                      tcr==0x22a5192519ull &&
                      ttbr0==0x8117a000ull &&
                      ttbr1==0x8117b000ull &&
                      mair==0x0c08044f00bb44ffull &&
                      !(sctlr&1ull) &&
                      r0==0x8117c003ull &&
                      r1==0x8117d003ull &&
                      rf==0x8117e003ull &&
                      p8==0x81000601ull &&
                      h38==0x81000601ull &&
                      f1==0x6000005e600605ull &&
                      f2==0x6000005e800605ull &&
                      !tail && last!=0 &&
                      elr==0x8142e004ull &&
                      (spsr1&0xfu)==4u);
    const unsigned expected_el_mode=5u;
#else
    const unsigned expected_el_mode=5u;
#endif
    stage20b_hvc_ok=((esr>>26)==0x16u &&
                     (esr&0xffffu)==0x21u &&
                     (spsr&0xfu)==expected_el_mode);
    mark(0x20b3,esr,elr,spsr);
}
#endif
#endif
void stage19_fault(uint64_t esr,uint64_t elr,uint64_t far)
{
    if(faulted) for(;;) __asm__ volatile("wfe");
    faulted=1;
    mark(S19_FAULT,esr,elr,far);
    if(online) drain(2500);
    for(;;) __asm__ volatile("wfe");
}
