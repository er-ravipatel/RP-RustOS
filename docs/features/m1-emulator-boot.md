# M1 emulator startup slice

Status: implemented and checked in QEMU on 2026-11-01. This vertical slice is tracked separately from the broader initial subsystem outlines.

Requirements: ELF entry at the selected address; EL1-only startup; aligned private stack and vector table; BSS clearing and initialized-data preservation; bounded polling serial output; normal/expected-panic diagnostics; unexpected exceptions/panics must not pass startup verification.

Design and scope: [startup contract](../kernel-startup-contract.md), [confirmed verification policy](../verification-publication-review.md), and [P4 evidence](../p4-verification.md). Review was Codex implementation self-review in two passes, not independent human approval.

Implementation: [kernel](../../core/kernel/src/main.rs), [entry assembly](../../core/kernel/src/entry.S), [linker layout](../../core/kernel/link.ld), [HAL](../../hal/src/lib.rs), [PL011](../../drivers/console/src/lib.rs), and [QEMU BSP](../../bsp/qemu-virt/src/lib.rs).

Acceptance: the five emulator checks and ELF inspections in the final P4 record passed. The development harness is not the production assembler runner. Images, interactive input, memory allocation, scheduling, userland and physical board support remain later work.
