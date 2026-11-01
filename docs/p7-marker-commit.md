# P7 approved final marker commit implementation

2026-11-01. D23 approved by the user and implemented. [Design baseline](m2-marker-commit-review.md), [kernel source](../bsp/rpi-zero2w/kernel/src/main.rs).

Normal commits RUSTOS_BOOT_OK; panic-test commits RUSTOS_EXPECTED_PANIC. Engineering diagnostics remain nonaccepting lines. The panic artifact never emits the normal token. The selected token is written without LF, then boundedly drained. Prefix write failure parks at stage 10; prefix drain failure at stage 11; final-LF enqueue failure at stage 12. Each leaves no complete acceptance line. After enqueueing LF, the exact assembly tail is DSB SY, debugger commit marker, then direct branch to a byte-verified stackless park. No later status poll or fallible call follows. Host receipt of LF provides the approved last-byte delivery evidence; there is no claim of a later BUSY-clear observation.

## Verification

[All 12 controlled cases pass](evidence/p7-marker-commit-controlled.json): each normal/panic variant succeeds with its exact token, and failures cover ordinary diagnostic TX/drain plus token-prefix TX, prefix drain and final-LF enqueue. Every failure checks exact park/stage, captured bytes and absence of a complete token. Neither variant emits its opposite token. Inputs remain explicitly synthetic measured-rate snapshots and RAM-backed UART faults, not unmodified firmware or hardware success.

The canonical Rust marker classifier now also tests Pi diagnostic prefixes, complete/unterminated token lines and opposite/contradictory tokens. All 34 current assembler Rust tests pass. Five analyzer test methods and panic-target Clippy with warnings denied pass. A combined entry-only/panic-test feature build is explicitly rejected so a debugger checkpoint artifact cannot masquerade as the panic variant.

The linked [normal](evidence/p7-marker-commit-stack-normal.json) and [panic](evidence/p7-marker-commit-stack-panic.json) audits verify the exact final commit tail and all reachable paths. Bounds remain 464 bytes for console and 21,440 bytes for the maximum boot phase, within 65,536 bytes. These are artifact-specific self-reviewed instruction-model bounds.

The [unmodified default run](evidence/p7-marker-commit-unmodified.json) still rejects QEMU's incomplete measured-rate reply at stage 4 and emits no token or serial bytes. [Five entry-only regressions](evidence/p7-marker-commit-entry.json) still pass multicore/BSS checks. Synthetic marker success is not a physical acceptance result.

## Remaining integration

Next reconcile the logical kernel module/source provenance with the actual Pi kernel target and introduce the typed Pi assembler build path, preserving the schema-2 bundle contract and pending-backend guard until complete image packaging/inspection exists. No partial ELF build may claim a complete Pi bundle. M2 physical measured-clock support, SD images and normal/panic hardware captures remain pending. Unexpected Rust panics remain silent; the intentional panic variant exercises the explicit fatal diagnostic routine. M1 and approved asset-lock bytes are unchanged.
