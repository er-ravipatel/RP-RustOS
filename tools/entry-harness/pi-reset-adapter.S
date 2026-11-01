// QEMU-only EL3 adapter. Never link this into a Pi image.
.section .text.entry,"ax"
.global reset_adapter
reset_adapter:
    msr daifset, #15
    mov x9, #0x531
    msr scr_el3, x9
    msr cptr_el3, xzr
    mov x9, #0x80000000
    msr hcr_el2, x9
    ldr x9, =0x30c50830
    msr sctlr_el2, x9
    mov x9, #0x3c9
    msr spsr_el3, x9
    mov x9, #0x200000
    msr elr_el3, x9
    mov x0, #0x1000000
    eret
