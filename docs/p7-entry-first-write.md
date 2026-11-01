# P7 observed test-only first write

2026-11-01. Added an isolated write experiment behind `TEST_WRITE`; normal preflight suites do not enable it. [Assembly](../tools/entry-harness/handoff.S), [runner](../tools/test_entry_first_write.py), [linker](../tools/entry-harness/link.ld), [retained evidence](evidence/p7-entry-first-write.json). This is not production stack initialization.

The linker defines a test stack interval [0x3f0000,0x400000), requires all harness image content below it and fixes entry at 0x200000. After the enabled preflight phases, the write variant sets SP to the linker-defined top and executes one labelled `str x9,[sp,#-16]!`. There is no call to Rust, BSS clear or further stack activity. The test marker is 0x1122334455667788.

## Runtime observation

The host connects only to its own QEMU GDB stub on loopback, selects CPU0 and initializes 32 sentinel/guard bytes at 0x3fffe0 before guest execution. Those debugger writes are fixture preparation, not startup writes. It then installs a write watchpoint over [0,0x20000000), with no fallback if the emulator rejects it.

The valid fixture stops with a write-watchpoint event at the exact labelled store; SP is 0x400000 and the sentinel is still unchanged. QEMU reports the watched range base (`watch:0`), not the access address; the PC, linked instruction, operand and memory checks establish the intended destination. The host removes the watchpoint and single-steps the store. PC advances four bytes, SP becomes 0x3ffff0, exactly eight bytes contain the expected little-endian marker and the surrounding 24 guard bytes remain unchanged.

Three negative fixtures—zero RAM, a reserved byte at the proposed stack write and an invalid CMA request—never trigger the watchpoint. After a bounded two-second observation the host interrupts and requires the exact failure marker/park PC, unchanged SP=0 and unchanged guard bytes. Thus silence/timeout alone cannot pass a rejection case. This observes CPU0 writes within the watched RAM window, not all cores, external DMA or arbitrary MMIO outside that range.

## Compiled checks and limits

The compiled image is also decoded through QEMU. The complete preflight code extent must contain exactly one store at `first_test_write`, exactly one SP setup at `stack_pointer_setup`, and otherwise only the existing read-only instruction allowlist without SP/WSP operands. Literal data is excluded from the code extent. All four runtime cases and all four instruction checks pass. The first protocol assertion expected the access address in the stop packet; inspection showed QEMU's range-base encoding and the assertion was corrected before the suite was reported passing.

This is evidence for one controlled emulator store, not proof of a complete 64 KiB call stack, stack-depth usage, pre-BSS Rust ABI/panic safety, production CPU masks/full affinity, firmware stability, multicore isolation or physical boot. Conservative one-bank/one-reservation-child limits remain. The approved firmware and accepted M1 workspace are unchanged. Do not turn the test write conditional into production startup without the remaining reviews.

Next: review the exact Cortex-A53 register/transition contract and pre-BSS Rust call requirements; extend write-observation cases when integrating a real validation call. Physical board setup remains deferred until software acceptance is ready.

After adding linker stack bounds, all five preflight suites also pass: [26 RAM](evidence/p7-entry-first-write-ram.json), [18 static](evidence/p7-entry-first-write-static.json), [19 CMA](evidence/p7-entry-first-write-cma.json), [four full-tree models](evidence/p7-entry-first-write-pinned.json) and [58 earlier entry cases](evidence/p7-entry-first-write-regression.json).
