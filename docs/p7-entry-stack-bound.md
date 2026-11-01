# P7 linked validator stack bound

2026-11-01. The remaining stack check is satisfied for the four exact test ELFs below. Production entry is still not wired; future artifacts must be audited again.

## Result

[Runtime evidence](evidence/p7-entry-stack-runtime.json) and exact linked audits:

| ELF case | Conservative bound including caller | Reachable functions | Audit |
| --- | --- | --- | --- |
| No CMA request | 21,440 bytes | 24 | [Report](evidence/p7-entry-stack-no_pool.json) |
| Valid CMA pool | 21,440 bytes | 24 | [Report](evidence/p7-entry-stack-cma_pool.json) |
| Insufficient CMA space | 21,440 bytes | 24 | [Report](evidence/p7-entry-stack-cma_no_space.json) |
| Explicit Rust panic | 21,440 bytes | 26 | [Report](evidence/p7-entry-stack-rust_panic.json) |

The 65,536-byte stack budget leaves 44,096 bytes beyond this conservative bound. All four runtime cases also pass their existing ABI/guard/panic checks and CPU0 outside-stack write watchpoints. The earlier 21,280-byte observed write extent is a distinct measurement, not the basis for the bound.

## Method and first review

The [checker](../tools/check_entry_stack.py) reads function extents from the linked ELF and obtains instruction disassembly from the paused QEMU instance loaded with that exact artifact. Reports bind the ELF and analyzer SHA-256 hashes and QEMU identity. It starts at the exported validator and, when linked, the explicit panic trigger; follows every direct call and tail edge; and includes reachable memory, slice-failure, panic-format and panic-handler functions. Formatting functions present in the ELF but not called by these roots are excluded. Panic arguments can contain formatting pointers, but the reviewed unformatted handler does not invoke them.

Within each function, it sums all immediate stack allocations, deliberately overcounting mutually exclusive paths. It checks the control-flow graph for stack-changing cycles, balanced incoming/outgoing SP at returns, consistent depth at joins and aligned calls. Across functions it uses the longest acyclic call path, conservatively retaining a caller frame even when a tail call releases it. Indirect calls/branches, unknown targets, recursion, dynamic SP operations, unsupported stack writeback, unreviewed fallthrough and allocation-bearing cycles reject the audit rather than produce a bound.

The actual labelled assembly caller is separately checked for exactly one 48-byte allocation/restoration, only approved direct calls within that frame, and rejection branches to the stackless failure park. The panic terminal is verified as exact WFE/branch bytes. The maximum path goes through the full validator, memory extraction, tree walk, its semantic callback and a core slice-panic path before reaching the unformatted park.

## Second review and checker verification

The [adversarial checker tests](../tools/test_entry_stack_checker.py) pass four test methods with multiple subcases: known direct calls/tails and nonreturning panic tails; rejection of dynamic SP, allocation/deallocation loops, recursion, indirect control flow, unknown targets, below-SP access, dynamic writeback, nonstandard return, missing restoration and returning fallthrough.

Review found that a simple backward address interval could wrongly classify a cold error branch crossing an epilogue as an allocation loop. The implementation now tests actual control-flow cycles, respecting returns and unconditional branches. It also checks return restoration so a repeated call cannot accumulate a hidden frame. These are self-review passes, not independent formal verification.

## Scope and carry forward

This is an instruction-model bound for these hashed linked ELFs and the reviewed caller. It relies on correct disassembly and standard AArch64/compiler ABI behavior. It is not a proof of arbitrary data-pointer safety, physical firmware, asynchronous exception handling, or a future build. Stackless fault vectors and masked interrupt state remain separate reviewed entry requirements. Unsupported future code generation must fail or receive a new review.

The actual Rust-call runner now requires the linked stack audit for every generated case. The earlier source-only inventory, which included a different code-generation layout and page-probing loop, remains research evidence; it must not be substituted for this linked-artifact result.

Next: wire the approved Pi-specific production entry and validator sequence, then rerun production disassembly, linked stack, pre-BSS write-order and emulator acceptance checks. Physical Zero 2 W UART normal/panic acceptance remains pending separately. M1 completion, its immutable artifacts and the approved asset lock are unchanged.
