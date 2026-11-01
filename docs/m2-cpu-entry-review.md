# M2 Cortex-A53 entry and pre-BSS Rust interface

2026-11-01. **D21 approved by the user.** Two self-review passes completed. This document records the approved design and acceptance gates; implementation evidence is tracked separately.

## Proposed sequence

Use a separate Pi entry. Require EL2 and a Cortex-A53 MIDR implementer/architecture/part match (`MIDR & 0xff0ffff0 == 0x410fd030`); do not assume a physical revision from the reference manual. Require primary affinity zero using all MPIDR affinity fields (`0xff00ffffff`); park other cores before writes. Require inherited SCTLR_EL2 M/C/I and EE clear. Reject unexpected live translation/cache/endianness state instead of attempting to disable it.

Install aligned, stackless EL2 fault vectors before DTB reads. Perform the bounded register-only DTB/RAM/reservation proof already explored by the [entry harness](p7-entry-first-write.md), including the entire kernel and 64 KiB private stack budget. Only after that proof may entry establish stack state or write RAM.

Configure the following Cortex-A53 baseline, install separate EL1 fault vectors and SP_EL1, then ERET to EL1h **before calling the full Rust validator**. This specifies the previously open placement of the Rust call; the test harness currently remains at EL2 and is not production evidence for this transition.

| Register | Proposed value | Purpose |
| --- | --- | --- |
| HCR_EL2 | `0x80000000` | EL1 AArch64; stage 2 and optional traps/routing disabled. A53 bit 29 stays clear. |
| CPTR_EL2 | `0x33ff` | Required RES1 fields, FP/SIMD trap clear. |
| HSTR_EL2 | `0` | No AArch32 system-register traps. |
| CNTHCTL_EL2 | `3` | Permit EL1 physical counter/timer access. |
| CNTVOFF_EL2 | `0` | No virtual counter offset. |
| VPIDR_EL2 / VMPIDR_EL2 | MIDR_EL1 / MPIDR_EL1 | Mirror physical identity. |
| SCTLR_EL1 | `0x30d00808` | A53 RES1 baseline plus SP alignment checking; little endian, MMU/data/instruction caches disabled. |
| CPACR_EL1 | `0x300000` | FPEN=3; permit FP/SIMD instructions before compiler-generated Rust code. |
| VBAR_EL1 | Dedicated 2 KiB aligned vector table | Stackless fault park reads ESR_EL1/ELR_EL1/FAR_EL1. |
| SP_EL1 | Linker stack top, aligned to 16 bytes | Inside the proven private stack budget. |
| SPSR_EL2 | `0x3c5` | EL1h, DAIF masked. |
| ELR_EL2 | Dedicated EL1 entry label | Controlled landing point. |

Mask DAIF at entry. Use ISB after control/vector changes and DSB SY plus ISB before the final ERET; verify the actual assembled sequence and register readback in the implementation tests. Disable EL1 physical/virtual timer controls before the Rust call; no timer interrupts are enabled by M2 entry. Inherited EL3 permissions must allow this execution (including FP/SIMD); EL2 cannot repair EL3 configuration. A trapped access parks through the appropriate fault vector and fails acceptance.

## Explicit Rust interface

Use `extern "C" fn validate(ptr: *const u8, len: usize, out: *mut BootMemoryResult) -> u32`, with x0/x1 carrying the already bounded DTB and x2 pointing to a 16-byte stack result buffer. Use a `#[repr(C)]` result with two u64 fields, CMA base and size. Return a status in w0; write output only on success. Allocate and initialize the aligned buffer only after stack safety is established. Preserve DTB base/length in callee-saved registers and retain selected CMA information across BSS initialization.

No implicit Rust aggregate return layout is assumed. The validator and every reachable helper must work before BSS: no heap, logging, TLS, mutable globals or platform buffers; use an unformatted panic park. Inspect generated calls, memory operations and stack use within the 64 KiB budget. A soft-float target name alone does not establish absence of FP/SIMD instructions.

Run full board/tree/RAM/static/dynamic reservation checks at EL1, including deterministic CMA placement. Insufficient CMA space can fail after stack setup but must fail before BSS initialization. Clear BSS and initialize console/boot information only after full success.

## Review pass 1: architecture and ABI sources

Cross-checked the [Arm Cortex-A53 TRM DDI0500J](https://documentation-service.arm.com/static/6040c321ee937942ba301626), especially SCTLR_EL1, HCR_EL2, CPTR_EL2 and CPACR_EL1. The A53 reserved-bit requirements matter: CPTR_EL2 cannot simply be zero; a generic HCR value containing bit 29 is unsuitable for this baseline.

Independently recomputed SCTLR_EL1 RES1 as bits 29,28,23,22,20,11 (`0x30d00800`), then added SA bit 3. CPTR_EL2 bits 13,12,9:0 sum to `0x33ff`. Checked against [pinned Trusted Firmware-A definitions](https://github.com/TrustedFirmware-A/trusted-firmware-a/blob/9799b799fb51edef36607bcd534b5510aa4156bc/include/arch/aarch64/arch.h).

The [pinned AAPCS64](https://github.com/ARM-software/abi-aa/blob/36203f2c4b9fa6be058a5a9e94ea508ff1effc52/aapcs64/aapcs64.rst) specifies indirect aggregate result storage via x8 when a result cannot be returned in argument registers. Thus a three-word Rust result must not be presumed to return in x0-x2. An explicit output pointer and scalar status make this boundary inspectable. Source hashes are retained in the [manifest](../out/research/cpu-entry-review/sources.json).

## Review pass 2: repository and failure paths

Compared the proposal with D16/D20, the isolated BSP validator and the compiled test-only entry. The current harness proves selected stackless preflight paths and one guarded write at EL2; it does not establish EL1 control state, a production Rust call, bounded compiled Rust stack depth or physical firmware behavior. Its low-byte secondary-core check must be replaced with the full affinity policy for production. EL2 fault handlers cannot be reused unchanged at EL1.

Required implementation evidence before accepting production entry:

- EL2-to-EL1 register readback, DAIF and SP alignment, plus a controlled FP/SIMD instruction test.
- Full-affinity secondary parking; wrong MIDR/EL, cache/MMU/EE entry rejection and correct EL1 fault-vector behavior.
- Explicit ABI output/guard bytes, callee-saved register preservation and validator failure/panic paths.
- No BSS/global writes before successful full validation; bounded stack usage including all generated helper calls.
- Existing preflight differential suites, pinned DTB models and first-write regression remain passing.

Both reviews are self-review, not independent review or hardware proof. D21 approval would permit implementation and emulator verification of this baseline. Physical Zero 2 W normal/panic acceptance and UART setup remain pending. M1 completion and the approved boot asset lock are unchanged.
