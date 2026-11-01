// Generated from reviewed harness sources; run tools/sync_pi_entry_sources.py --check.
    mov x9, #0x80000000
    msr hcr_el2, x9
    mov x9, #0x33ff
    msr cptr_el2, x9
    msr hstr_el2, xzr
    mov x9, #3
    msr cnthctl_el2, x9
    msr cntvoff_el2, xzr
    mrs x9, midr_el1
    msr vpidr_el2, x9
    mrs x9, mpidr_el1
    msr vmpidr_el2, x9
    ldr x9, =0x30d00808
    msr sctlr_el1, x9
    mov x9, #0x300000
    msr cpacr_el1, x9
    adr x9, el1_vectors
    msr vbar_el1, x9
    ldr x9, =__stack_top
    msr sp_el1, x9
    mov x9, #0x3c5
    msr spsr_el2, x9
    adr x9, el1_landing
    msr elr_el2, x9
    isb
    // Read every owned EL2 control and EL1 landing register before ERET.
    .macro check_register name, value
    mrs x9, \name
    ldr x14, =\value
    cmp x9, x14
    b.ne failed
    .endm
    check_register hcr_el2, 0x80000000
    check_register cptr_el2, 0x33ff
    check_register hstr_el2, 0
    check_register cnthctl_el2, 3
    check_register cntvoff_el2, 0
    check_register spsr_el2, 0x3c5
    check_register sp_el1, __stack_top
    check_register vbar_el1, el1_vectors
    check_register elr_el2, el1_landing
    mrs x9, vpidr_el2
    mrs x14, midr_el1
    cmp x9, x14
    b.ne failed
    mrs x9, vmpidr_el2
    mrs x14, mpidr_el1
    cmp x9, x14
    b.ne failed
    dsb sy
    isb
    mrs x9, cntkctl_el1
    cbnz x9, failed
    mrs x9, cntp_ctl_el0
    tst x9, #3
    b.ne failed
    mrs x9, cntv_ctl_el0
    tst x9, #3
    b.ne failed
    eret
el1_landing:
    mrs x11, CurrentEL
    cmp x11, #4
    b.ne failed
    msr cntp_ctl_el0, xzr
    msr cntv_ctl_el0, xzr
    msr cntkctl_el1, xzr
    isb
    mrs x9, sctlr_el1
    ldr x14, =0x30d00808
    cmp x9, x14
    b.ne failed
    mrs x9, cpacr_el1
    cmp x9, #0x300000
    b.ne failed
    mrs x9, daif
    cmp x9, #0x3c0
    b.ne failed
    mov x9, sp
    ldr x14, =__stack_top
    cmp x9, x14
    b.ne failed
    // A real SIMD instruction tests the permission path, not just its register.
    movi v0.16b, #0x5a
    umov x9, v0.d[0]
    ldr x14, =0x5a5a5a5a5a5a5a5a
    cmp x9, x14
    b.ne failed
    b el1_checked
el1_fault:
    mrs x14, esr_el1
    mrs x15, elr_el1
    mrs x16, far_el1
    mov x10, #0xf00d
    b fault_park
.balign 2048
el1_vectors:
.rept 16
    b el1_fault
    .fill 31, 4, 0xd503201f
.endr
el1_checked:
