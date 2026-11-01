# P7 controlled emulator EL2 handoff

2026-11-01. Built and executed an isolated test-only assembly adapter on QEMU `raspi3b`. It lives under tools, outside the production BSP and accepted M1 workspace. [Runner](../tools/test_entry_handoff.py), [assembly](../tools/entry-harness/handoff.S), [linker](../tools/entry-harness/link.ld).

The ELF is linked at 0x200000 and loaded explicitly through QEMU's generic loader on CPU 0. Starting in the previously observed EL3 reset environment, the adapter sets test-only SCR/SCTLR/SPSR state, supplies synthetic x0=0x1000000 and executes ERET. At EL2 it checks CurrentEL and M/C/I bits, then leaves a marker in x10 and parks. It contains no intentional stack or data-store instructions, but no write-trace/disassembly audit has yet established that property at runtime.

Recorded checks passed: marker x10=0x50415353, x11 CurrentEL=8, x12 preserved pointer=0x1000000, x13 SCTLR_EL2 M/C/I clear, and observed PSTATE EL2h. QMP stops the emulator after a bounded run and captures registers, memory tree, command and version. The runner records exact build commands plus source/ELF hashes in a fresh report. Its 200 ms run interval is a bounded observation window, not a performance guarantee; missing markers fail.

The initial successful report is [raw evidence](../target/entry-handoff-1793511541570910900/report.json). Its captured register field was originally named `reset_registers` by the reused probe; these are post-execution registers, not reset state. Subsequent runner reports use `observed_registers` to avoid that ambiguity.

The rerun with the clarified field also passed all five checks; its [retained dashboard evidence](evidence/p7-entry-handoff.json) preserves the current report independently of build-directory cleanup.

This uses published Pi stub values as emulator-adapter inputs, not approved production CPU masks. It does not execute the pinned firmware or production kernel, read a DTB, establish safe writable RAM, use a UART, enter EL1, validate secondary cores or demonstrate physical Zero 2 W support. Only CPU 0 was observed. The MPIDR low-byte check is test-specific and is not the full production affinity check required by the entry design.

Next: add controlled failure fixtures and observe their park locations, then disassemble and trace the read-only preflight prototype before introducing stack writes. Full register allocation and exact EL2-to-EL1 control-state review remain open. This is a harness foundation, not completion of D16 or P7.
