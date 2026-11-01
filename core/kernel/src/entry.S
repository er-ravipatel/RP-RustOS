.section .text.entry,"ax"
.global _start
.type _start, %function
_start:
    msr daifset, #15
    mrs x0, CurrentEL
    cmp x0, #4
    b.ne early_halt
    mrs x0, sctlr_el1
    mov x1, #0x1005
    tst x0, x1
    b.ne early_halt
    msr SPSel, #1
    adrp x0, __stack_top
    add x0, x0, :lo12:__stack_top
    mov sp, x0
    mov x29, xzr
    mov x30, xzr
    // Permit FP/SIMD before entering Rust, even with a soft-float ABI.
    mrs x0, cpacr_el1
    orr x0, x0, #0x300000
    msr cpacr_el1, x0
    isb
    adrp x0, __bss_start
    add x0, x0, :lo12:__bss_start
    adrp x1, __bss_end
    add x1, x1, :lo12:__bss_end
    // Poison the actual sentinel so Rust's check exercises our own clear.
    adrp x3, BSS_SENTINEL
    add x3, x3, :lo12:BSS_SENTINEL
    mov x2, #0x5a
    str x2, [x3]
    cmp x0, x1
    b.hs 2f
1:
    cmp x0, x1
    b.hs 2f
    str xzr, [x0], #8
    b 1b
2:
    adrp x0, vectors
    add x0, x0, :lo12:vectors
    msr vbar_el1, x0
    isb
    bl kernel_main
early_halt:
    wfe
    b early_halt

.section .text.vectors,"ax"
.balign 2048
.global vectors
vectors:
.rept 16
    b exception_entry
    .balign 128
.endr
exception_entry:
    msr daifset, #15
    mrs x0, esr_el1
    mrs x1, elr_el1
    mrs x2, far_el1
    b kernel_exception
