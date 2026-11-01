# P7 malformed-memory checks and reservation-tree guard

2026-11-01. Tightened the narrow RAM prototype and extended the shared fixtures. [Assembly](../tools/entry-harness/handoff.S), [comparison runner](../tools/test_entry_ram.py), [retained report](evidence/p7-entry-ram-guards.json).

The optional RAM pass now explicitly rejects a root `reserved-memory` node rather than reporting RAM-only success while ignoring its contents. This is a temporary conservative guard, not a static/dynamic tree-reservation implementation. In particular, firmware trees containing the pinned CMA request remain rejected here until its register-only validation is implemented. D20 remains approved and implemented in the Rust validator; this guard does not undo that decision.

The comparison suite now has 24 passing cases. Nine added cases cover missing/incorrect/unterminated device type, unterminated status, missing/truncated reg, a valid static reservation, a static kernel collision and the known dynamic CMA request. Every case supplies identical bytes to the host checker and emulator. The report explicitly labels three conservative differences: multiple valid banks, a valid static tree and a valid CMA tree are accepted by Rust but rejected by the current assembly subset. The unsafe reserved-kernel case fails in both paths. Remaining cases agree on their acceptance/rejection expectations.

The guard compares the complete checked root-child node name, including its terminator; it does not interpret a substring as the reserved-memory parent. The earlier full structure/duplicate pass continues to establish safe traversal bounds. No stack, call, store or scratch-memory requirement was added. All compiled-code/vector/park checks pass for the RAM suite.

The shared fixture generator gained explicit device-type and reg overrides so malformed cases are reproducible. It remains host/test code and no production input schema changed. The original 14 host-reference cases were rerun and pass. The existing 58-case emulator suite is recorded separately after regression verification.

All 58 regression scenarios passed; [retained regression evidence](evidence/p7-entry-ram-guards-regression.json).

Next implementation gate: replace the blanket reserved-memory rejection only when its parent cell/ranges rules, active static child ranges, kernel conflicts, header/tree interactions and the approved dynamic request shape have bounded checks and negative tests. Until then, do not wire a first stack write or emit production startup success. Arbitrary malformed node identities, multiple-bank support, data-abort coverage, final CPU masks, full affinity and write tracing remain open. No physical Pi or SD media operation occurred.
