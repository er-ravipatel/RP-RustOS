# P7 stackless Pi entry design checkpoint

2026-11-01. Implementation design under approved D16/D20; not executable entry code or completed register review. The existing QEMU entry remains unchanged. This document defines obligations for the next implementation slice, not evidence of their fulfillment.

## Entry phases and first-write boundary

1. Mask DAIF and preserve x0. Check CurrentEL before accessing EL2-only registers. Accept EL2 only. Read MPIDR affinity fields; park non-primary cores without shared writes. Do not infer the primary from only a truncated arbitrary CPU identifier. The Zero 2 W expected affinity must be explicit in code and fixtures.
2. Check inherited SCTLR_EL2 M/C/I state and supported little-endian execution. Reject unexpected state; do not disable a live translation/cache regime. Install a 2 KiB aligned, read-only EL2 vector table whose entries branch to a register-only park loop. No exception handler may push registers, log or return. Setting VBAR is a register operation; the vector bytes must already be in the loaded image. DAIF masking alone does not handle synchronous data aborts.
3. Validate the claimed DTB pointer before each class of load: minimum address, alignment, checked header end below the board ceiling and disjoint from the entire kernel budget. Read the bounded header, then validate total extent, blocks, structure and strings before dependent loads. All integer fields are big-endian. The ceiling is only an addressability filter: firmware must have initialized readable RAM. A synchronous fault must park through the early vectors; a bounded capture timeout is failure. This is not a proof that arbitrary physical addresses are safe to read on every platform.
4. Perform bounded register-only tree passes and header-reservation scans to establish that the complete kernel reservation and DTB each fit a declared active ARM RAM bank, and that no addressed reservation overlaps the kernel. Reject missing/zero RAM, malformed or duplicate relevant properties, unsupported mappings/status/cell widths and all unhandled reservation forms. Recognize and validate D20's dynamic request shape but do not allocate its pool yet: the request has no physical location until our own selection. Never skip an unrecognized dynamic request.
5. Only after that proof, establish the linker-defined private stack. Stack alignment and containment in [0x200000,0x400000), disjoint BSS placement and flat-image entry/layout must have linker and host checks. The first stack store is the first permitted RAM write by startup. No temporary firmware stack, low-memory scratch space, BSS scratch array or advertised-RAM-size fallback is allowed.
6. With the safe stack, call a dedicated no-global Rust validator on the original bounded DTB. It must run without heap, UART, BSS reads, TLS, panic formatting or implicit platform services. Review its generated code and helper calls; a no_std annotation alone is insufficient. It repeats full validation and selects/reserves the D20 pool. Failure branches to the silent park path; panic must not use an uninitialized console. Preserve boot results in callee-saved registers or the validated stack, never in BSS that is about to be cleared.
7. After successful validation, apply the reviewed EL2-to-EL1 control/trap/timer state, use EL1h with DAIF masked, preserve DTB/pool values, and enter EL1. Install stackless early EL1 vectors before any potentially faulting EL1 operation. Clear BSS without touching the live stack or preserved results, enable required FP/SIMD permissions before Rust that may need them, initialize boot information and the board console, then emit startup success. No MMU/cache/multicore feature is added.

The exact location of the Rust validation call relative to ERET is a register-level implementation choice: this checkpoint proposes validating at EL2 with a safe private stack. The dedicated validator must not assume an EL1 environment. Do not reuse the current QEMU `kernel_main` as this validator.

## Register ownership for the preflight prototype

| Registers | Reserved role |
| --- | --- |
| x19 | Original DTB pointer, unchanged throughout preflight |
| x20 | Checked DTB end |
| x21/x22 | Structure start/end |
| x23/x24 | Strings start/end |
| x25 | Token cursor |
| x26 | Token/depth/pass budget state, representation to be specified |
| x27/x28 | Current relevant node/property offsets, representation to be specified |
| x0–x17 | Explicit scratch and routine arguments; document clobbers at every helper |
| x18 | Reserved; avoid platform-register assumptions |
| x29 | Unused before stack; zero before entering ordinary Rust |
| x30 | One leaf helper return address only; no nested BL without a separate register plan |
| SP | Unused until phase 5 |

This is a register allocation outline, not a claim that the full parser fits it. The full assembly specification must enumerate live values and clobbers for each pass before code is accepted. Read-only rescans can replace arrays; every rescan needs its own explicit finite limit. No recursion. Cap DTB bytes at 2 MiB, depth at 16, tokens at 16,384, properties per node at 256 and addressed reservations at 128. Multiple-pass duplicate/overlap checks need a documented total work bound and measured emulator runtime. If the plan cannot fit registers or practical time limits, revise the parser strategy explicitly rather than adding an unchecked stack.

## CPU register review gate

Before executable transition code, prepare a Cortex-A53/Armv8-A table for SCTLR_EL1/EL2, HCR_EL2, CPTR_EL2, HSTR_EL2, CNTHCTL_EL2, CNTVOFF_EL2, CPACR_EL1, SPSR_EL2, ELR_EL2, SP_EL1 and VBAR_EL1/EL2. For each, record reset/unknown assumptions, required RES0/RES1 bits, exact mask/value, purpose and instruction barriers. Preserve/initialize timer and virtualization identity state as required by the selected execution contract. Reviewed Redox/stub constants are comparison material, not automatically approved values. No exact transition mask is frozen by this document.

## Emulator/disassembly acceptance matrix

Use a separate harness and linker fixture without changing the accepted M1 workspace. QEMU virt with Cortex-A53 and EL2 enabled tests CPU/entry logic, not Pi firmware or peripherals. Inject explicit DTB fixtures at nonoverlapping addresses; use a controlled test adapter for the harness's RAM map, because QEMU virt RAM does not match Pi's low-memory physical map. Any Pi-layout memory backend must be documented and checked for device conflicts. Test adapters must never enter a production image.

Required cases: valid updated tree; unsupported EL; secondary core; enabled M/C/I state; invalid/misaligned/unreadable DTB pointer; truncated header; oversized/overflowing blocks; missing terminator/end token; excessive depth/properties/tokens; missing cells; duplicate relevant properties; zero/partial RAM; header/static reserved kernel byte; DTB/kernel overlap; supported CMA; malformed/constrained/duplicate CMA; insufficient pool space. A valid fixture must reach a harness-only success marker after validation; rejected fixtures must never reach it. Silence alone is not evidence that the intended check executed: retain emulator state/trace at the failure park location.

Instrument writes or use debugger watchpoints to establish no data writes before the first-write boundary and no protected-region writes on failure. Disassemble the preflight/vector sections and inspect for SP-relative operations, stores, compiler prologues, nested calls and unexpected helper references. Source grep alone is insufficient. Compare assembly results with the Rust validator: assembly may conservatively reject a documented subset but must not authorize a stack for a tree that violates kernel RAM/reservation safety. Pass the complete integration suite and M1 regressions before kernel wiring.

## Two self-review passes and remaining gaps

First pass compared D16/D20 with the AArch64 handoff documentation and existing bounded parser. Second pass traced the current QEMU assembly/linker and Rust validator's storage assumptions. Findings: QEMU overwrites incoming x0, requires EL1 and establishes stack/BSS early; it cannot be reused unchanged. The Rust parser has a sizeable frame array and therefore cannot be the pre-stack solution. DAIF does not replace synchronous exception vectors. A full RAM map cannot be inferred from the shipped zero-sized DTB placeholder.

Register liveness, bounded rescanning algorithm, precise architectural masks, pre-BSS Rust call dependencies and the emulator memory adapter remain open implementation gates. This checkpoint completes a design outline only; no stackless parser, CPU transition or Pi boot is marked complete.

References: [approved boot contract](m2-boot-contract.md), [D20](m2-cma-entry-review.md), [CMA implementation](p7-cma-reservation.md), [existing QEMU entry](../core/kernel/src/entry.S), [Linux AArch64 handoff comparison](https://docs.kernel.org/arch/arm64/booting.html), [Devicetree specification](https://www.devicetree.org/specifications/). Linux requirements are comparison material, not the RustOS boot specification.
