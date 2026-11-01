# P7 four-core execution experiment

2026-11-01. [Runner](../tools/test_entry_multicore.py), [passing evidence](evidence/p7-entry-multicore.json).

All four actual QEMU raspi3b Cortex-A53 cores are started at the same test entry. The original adapter low-byte MPIDR park is removed in this experiment so every core reaches the EL2 full-affinity gate. No identity, affinity or control values are injected.

Core 0 completes preflight and reaches the EL1 success park with SP=0x400000. Cores 1-3 reach the exact secondary park at EL2 with SP=0, X19=0 and marker zero. Source ordering places the gate before DTB loads and stack setup. No per-secondary write-watchpoint trace was collected.

The initial [failed observation](evidence/p7-entry-multicore-observation-discovery.json) exposed a test bug: human-monitor CPU selection did not persist across QMP requests, yielding CPU#0 repeatedly. The helper now uses explicit cpu-index on each request and tests the returned CPU identity. Only the corrected run counts as acceptance evidence.

Regressions pass: [58 preflight cases](evidence/p7-entry-multicore-preflight-regression.json), [14 CPU/EL1 cases](evidence/p7-entry-multicore-el1-regression.json), and [four Rust/panic cases](evidence/p7-entry-multicore-rust-regression.json) with outside-stack CPU0 watchpoints.

This establishes actual emulated secondary parking for these four cores. It does not establish physical Zero 2 W firmware behavior. The complete linked-helper static stack bound remains open; observed usage and source frame inventory are insufficient. Production wiring and physical acceptance remain pending.

The subsequent [linked stack audit](p7-entry-stack-bound.md) satisfies the stack-bound gate for its four exact test artifacts; production artifacts still require a new audit.
