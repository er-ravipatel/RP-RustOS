// Firmware entry: EL2, x0 points to the firmware-updated DTB.
.arch armv8-a+simd
.section .text.entry,"ax"
.global _start
_start:
    msr daifset, #15
    mov x10, #0
    mrs x11, CurrentEL
    cmp x11, #8
    b.ne failed
// CPU guards and the complete register-only preflight follow in global_asm order.
