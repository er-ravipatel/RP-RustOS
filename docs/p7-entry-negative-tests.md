# P7 harness negative tests and instruction inspection

2026-11-01. Extended the separate [entry harness](p7-entry-handoff.md), not production startup. [Retained report](evidence/p7-entry-negative-tests.json) includes all commands, ELF/source hashes, linked symbols, QEMU version, observed registers and decoded instructions for three fresh executables.

| Scenario | Required result | Observed |
| --- | --- | --- |
| Normal EL2h, M/C/I clear | Success marker, CurrentEL=8, preserved synthetic DTB pointer, correct PSTATE and success park PC | Pass |
| Adapter deliberately enters EL1h | Failure marker, CurrentEL=4, EL1h and failure park PC | Pass |
| Adapter enters EL2h with SCTLR_EL2.I enabled | Failure marker, CurrentEL=8, EL2h and failure park PC | Pass |

The runner resolves success/failure park addresses from each linked ELF symbol table. It accepts only the WFE or branch instruction in the expected two-instruction park loop; a marker alone is insufficient. QEMU decodes every instruction from `_start` through `harness_code_end`, excluding the subsequent literal pool. An explicit instruction allowlist and operand check reject stores, calls and SP/WSP operands; the decoded count must match the linked code extent. All three executables pass these checks. This is compiled-code inspection, not an exhaustive runtime memory-write trace or proof of peripheral behavior.

The first EL1 fixture failed by trapping at 0x200, with no expected marker; the runner correctly reported failure. The adapter had not established AArch64 EL1 execution through HCR_EL2.RW and a known EL1 control state. After adding test-only setup, the fixture reaches the intended rejection loop. The earlier failed report remains under the build directory; only the successful final suite is retained here. These adapter register values do not approve production EL2-to-EL1 masks.

Limits: only CPU 0, one negative exception level and instruction-cache state were exercised. Secondary affinity, MMU/data-cache variants, synchronous-fault vectors, DTB loads, RAM/reservation parsing, stack safety and physical-board behavior remain pending. No production kernel was loaded and no SD media was accessed. M1 remains unchanged.

Next: prototype bounded read-only DTB header checks and a synchronous-fault park path, with readable/unreadable and malformed fixtures, before any stack writes. Keep the full [entry design](p7-stackless-entry-design.md) gates open.
