/* First diagnostic Cactus userspace process. Source-built, static arm64. */
/* Native syscalls use x16 and svc #0x80, carry on error. */
#define SYS_write 4
#define SYS_open 5
#define SYS_getpid 20
#define SYS_select 93
#define O_RDWR 2

    .text
    .globl _start
    .p2align 2
_start:
    /* XNU does not promise a 16-byte-aligned initial stack. */
    mov x9, sp
    and x9, x9, #~15
    mov sp, x9

    /* Stage65: signal from real userspace before opening console. */
    mov x16, #SYS_getpid
    svc #0x80

    adr x0, console_path
    mov x1, #O_RDWR
    mov x2, #0
    mov x16, #SYS_open
    svc #0x80
    b.cs park
    mov x19, x0

    adr x1, greeting
    adr x2, greeting_end
    sub x2, x2, x1
    bl print

    mov x16, #SYS_getpid
    svc #0x80
    add w0, w0, #'0'
    sub sp, sp, #16
    strb w0, [sp]
    mov x1, sp
    mov x2, #1
    bl print
    add sp, sp, #16

    adr x1, greeting_end
    adr x2, heartbeat
    sub x2, x2, x1
    bl print

loop:
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x3, #0
    adr x4, five_seconds
    mov x16, #SYS_select
    svc #0x80
    adr x1, heartbeat
    adr x2, heartbeat_end
    sub x2, x2, x1
    bl print
    b loop

print:
    mov x0, x19
    mov x16, #SYS_write
    svc #0x80
    ret
park:
    b park

    .p2align 3
five_seconds:
    .quad 5
    .quad 0
console_path:
    .asciz "/dev/console"
greeting:
    .ascii "\n*** CACTARWIN XNU PID "
greeting_end:
    .ascii " started ***\n"
heartbeat:
    .ascii "CACTARWIN init: heartbeat\n"
heartbeat_end:
