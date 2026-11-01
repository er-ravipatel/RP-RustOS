// Generated from reviewed harness sources; run tools/sync_pi_entry_sources.py --check.
    mrs x9, midr_el1
    ldr x14, =0xff0ffff0
    and x9, x9, x14
    ldr x14, =0x410fd030
    cmp x9, x14
    b.ne failed
    mrs x9, mpidr_el1
    ldr x14, =0xff00ffffff
    tst x9, x14
    b.ne secondary_park
    mrs x9, sctlr_el2
    ldr x14, =0x2001005
    tst x9, x14
    b.ne failed
