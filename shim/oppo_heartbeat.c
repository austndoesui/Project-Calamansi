/* Short CPH2179 entry/CDC probe. No framebuffer, memory admission, watchdog,
 * payload loading, or XNU transfer. Runs only after the shim BSS is cleared. */
#include <stdint.h>
#include "cactus_usb.h"
#include "pmsg_trace.h"

static uint64_t counter(void)
{
    uint64_t value;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(value));
    return value;
}

static uint64_t frequency(void)
{
    uint64_t value;
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(value));
    return value ? value : 13000000u;
}

static void put_hex8(char *out, uint32_t value)
{
    static const char digits[] = "0123456789abcdef";
    for (unsigned i = 0; i < 8; ++i)
        out[i] = digits[(value >> ((7u - i) * 4u)) & 0xfu];
}

static void idle(void)
{
    for (;;) __asm__ volatile("wfe");
}

void oppo_cdc_heartbeat_main(uintptr_t dtb)
{
    uint32_t diagnostics[16] = {0};
    pmsg_trace_mark("CDC_BEGIN", dtb, 0, 0);

    /* usb_init validates the MUSB hardware ID before any PHY/controller
     * writes. A failed ID check is reported to pmsg and then stops. */
    if (!usb_init(diagnostics)) {
        pmsg_trace_mark("CDC_INIT_FAIL", diagnostics[1], diagnostics[2],
                        diagnostics[13]);
        idle();
    }
    pmsg_trace_mark("CDC_INIT_OK", diagnostics[1], diagnostics[2],
                    diagnostics[3]);

    static const char prefix[] = "OPPO6765 HB ";
    char line[32];
    unsigned n = 0;
    int noted_tx = 0;
    for (unsigned i = 0; i < sizeof(prefix) - 1; ++i)
        line[i] = prefix[i];
    line[sizeof(prefix) - 1 + 8] = '\n';
    const unsigned line_len = sizeof(prefix) - 1 + 9;

    uint64_t hz = frequency();
    uint64_t start = counter();
    uint64_t stop = start + hz * 20u;
    uint64_t next = start;
    while (counter() < stop) {
        usb_poll();
        uint64_t now = counter();
        if (usb_online() && now >= next) {
            put_hex8(line + sizeof(prefix) - 1, n);
            if (usb_send_budgeted((const uint8_t *)line, line_len) == 1) {
                if (!noted_tx) {
                    pmsg_trace_mark("CDC_FIRST_QUEUED", n, line_len, 0);
                    noted_tx = 1;
                }
                ++n;
            }
            next = now + hz / 2u;
        }
    }

    usb_shutdown();
    pmsg_trace_mark("CDC_DONE", n, noted_tx, 20);
    idle();
}
