# P7 narrow static reservation-tree pass

2026-11-01. Added an opt-in static reservation extension to the isolated stackless harness. [Assembly](../tools/entry-harness/handoff.S), [comparison runner](../tools/test_entry_static.py), [retained evidence](evidence/p7-entry-static-tests.json). The earlier RAM-only mode retains its blanket reservation-tree guard.

The new mode recognizes one root `reserved-memory` parent, requires explicit matching root address/size cell counts and empty `ranges`, and rejects parent `status` in line with the current Rust policy. It accepts at most one active static child containing one reg tuple, with supported missing/ok/okay/disabled status. Nested children, dynamic size requests and unsupported child properties are rejected conservatively. In particular, phandle/no-map/reusable and compatible-bearing static variants are not yet supported by this narrow prototype. It is not a general binding implementation.

The static tuple decoder checks positive size, arithmetic overflow, the board ceiling and any reserved byte in the full kernel budget. A bounded rescan compares it against every nonempty header reservation and rejects overlap, including exact duplicates. Header plus static reservation capacity is limited to 128; 127 header ranges plus one static range pass, while 128 plus one fail. Touching boundaries and a reservation containing the DTB are accepted. The complete structure/duplicate pass precedes these semantics; no scratch RAM or stack is introduced.

For this phase x24 selects memory, reserved parent or static child state. x22 stores parent mapping/seen/child flags after its earlier structure-end lifetime has finished. x14/x15 and x16/x17 are per-node state and reg extent; x29/x30 retain root cell widths. The single-active-child limit avoids an unbounded array or unimplemented tree-to-tree overlap scan. D20 CMA remains rejected pending its own register-only shape validation; its approved Rust implementation is unchanged.

All 18 static comparison cases pass. Coverage includes absent/low/DTB/touching reservations, two-cell encodings, reserved kernel byte, zero size, u64 wrap, board ceiling, mismatched cells, translated/missing ranges, parent status, header overlap/touch, combined capacity and continued dynamic rejection. Identical DTB bytes run through the host Rust checker. The valid dynamic request is the documented conservative difference: Rust accepts it; this prototype rejects it. Marker, exact park-PC, CPU/PSTATE, decoded instruction and vector checks pass for every case.

## Alignment fault found and corrected

The initial suite exposed real data aborts in two-cell static properties that were only four-byte aligned. Captured ESR_EL2=0x96000021 reports a same-level data abort with alignment fault; ELR identifies the eight-byte `ldr x1,[x16],#8`, and FAR identifies an address ending in 0x124. The stackless vector handler reached its expected fault loop, but those cases correctly failed their intended semantic result. These observations are retained as [diagnostic evidence](evidence/p7-entry-static-alignment-discovery.json), not a passing acceptance suite.

DTB properties are four-byte aligned; eight-byte cells must not assume eight-byte alignment in this MMU-off execution environment. The common address/size decoder now reads two aligned big-endian u32 cells and combines them. The static suite and all 24 RAM comparison cases then pass. This also improves the earlier RAM prototype, whose successful two-cell fixture happened to be aligned more generously.

This establishes observed alignment-data-abort routing for those failing fixtures, not general unreadable-memory abort coverage or a production fault handler. The earlier 58-case suite is rerun separately. No stack writes, production startup, final CPU-mask approval, full affinity, runtime write tracing, pinned firmware boot or physical media operation is claimed.

All [24 RAM regression cases](evidence/p7-entry-static-ram-regression.json) and [58 earlier emulator scenarios](evidence/p7-entry-static-regression.json) passed after the correction.

Next: bounded D20 request validation and malformed-node/variant coverage, then reconcile conservative limits with the actual handoff tree before considering a first-write boundary. M1 is unchanged and M2/P7 remain in progress.
