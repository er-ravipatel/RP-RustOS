// Test-only candidate for the production gate. Inserted before any DTB load.
    mrs x9, midr_el1
.ifdef TEST_MIDR
    ldr x9, =TEST_MIDR
.endif
    ldr x14, =0xff0ffff0
    and x9, x9, x14
    ldr x14, =0x410fd030
    cmp x9, x14
    b.ne failed
    mrs x9, mpidr_el1
.ifdef TEST_AFFINITY
    ldr x9, =TEST_AFFINITY
.endif
    ldr x14, =0xff00ffffff
    tst x9, x14
    b.ne secondary_park
    mrs x9, sctlr_el2
.ifdef TEST_CONTROL
    ldr x9, =TEST_CONTROL
.endif
    ldr x14, =0x2001005
    tst x9, x14
    b.ne failed
