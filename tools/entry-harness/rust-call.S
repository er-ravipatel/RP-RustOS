// Test-only AAPCS64 boundary after el1_checked. All stores use proven stack.
.global rust_call_begin
rust_call_begin:
    mov x19, x0
    ldr w20, [x19, #4]
    rev w20, w20
    mov x21, #21
    mov x22, #22
    mov x23, #23
    mov x24, #24
    mov x25, #25
    mov x26, #26
    mov x27, #27
    mov x28, #28
    mov x29, #29
    sub sp, sp, #48
    mov x9, #0xaaaa
    str x9, [sp, #8]
    stp x9, x9, [sp, #16]
    str x9, [sp, #32]
    mov x0, x19
    mov x1, x20
    add x2, sp, #16
.ifdef TEST_PANIC
    bl harness_force_panic
.endif
    bl rustos_validate_boot_memory
    mov w17, w0
    ldr x9, =TEST_DTB
    cmp x19, x9
    b.ne failed
    ldr w9, [x19, #4]
    rev w9, w9
    cmp x20, x9
    b.ne failed
    .irp n,21,22,23,24,25,26,27,28,29
    cmp x\n, #\n
    b.ne failed
    .endr
    mov x14, #0xaaaa
    ldr x9, [sp, #8]
    cmp x9, x14
    b.ne failed
    ldr x9, [sp, #32]
    cmp x9, x14
    b.ne failed
    ldp x23, x24, [sp, #16]
.ifdef TEST_REJECT
    cmp w17, #1
    b.ne failed
    cmp x23, x14
    b.ne failed
    cmp x24, x14
    b.ne failed
.else
    cbnz w17, failed
    ldr x9, =TEST_POOL_BASE
    cmp x23, x9
    b.ne failed
    ldr x9, =TEST_POOL_SIZE
    cmp x24, x9
    b.ne failed
.endif
    add sp, sp, #48
    mov x0, x19
    mrs x11, CurrentEL
    mrs x13, sctlr_el1
.global rust_call_end
rust_call_end:
