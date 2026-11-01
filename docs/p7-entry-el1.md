# P7 EL1 transition experiment and Rust ABI

D21 approved by the user on 2026-11-01. Implementation remains in progress.

The [test-only transition](../tools/entry-harness/el1-transition.S) executes after the existing stackless header/tree/board/RAM/static/CMA-shape preflight. It configures the D21 EL1 baseline, SP_EL1 and separate EL1 fault vectors, then uses ERET to EL1h. At EL1 it checks CurrentEL, SCTLR_EL1, CPACR_EL1, DAIF and exact stack top, disables timer controls and executes a real SIMD instruction with a checked result.

[QEMU evidence](evidence/p7-entry-el1.json): three cases pass on raspi3b. Normal reaches the success park at EL1 with SP=0x400000; a deliberate EL1 BRK reaches the EL1 fault handler with the expected syndrome; a zero-RAM declaration is rejected at EL2 with SP untouched. These are CPU experiments with synthetic handoff data, not Zero 2 W firmware or peripheral validation.

The [explicit Rust ABI](../bsp/rpi-zero2w/src/entry_abi.rs) now exposes a scalar status and explicit pointer to a repr(C), 16-byte CMA result. It calls the full memory validator and changes output only on success. Its unsafe contract requires the assembly caller to prove DTB readability, output ownership and stack safety. A guarded host test confirms malformed input leaves result and guards unchanged. BSP host tests: 36 passed; Clippy all targets with warnings denied and release AArch64 soft-float build passed.

## Remaining acceptance gates

The original transition-only experiment does not call Rust. A subsequent [actual EL1-to-Rust experiment](p7-entry-rust-call.md) now verifies that boundary. Production entry is not wired. Register readback coverage must expand to all owned EL2 settings; full-affinity secondary and incorrect CPU/control-state negative tests remain pending. Before promotion, verify the assembly/Rust call, valid output and preserved registers, no writes to BSS before validation, compiled helper/stack bounds, and fault/panic paths. Early CPU guards in the production path must precede DTB reads; this transition experiment performs its additional MIDR/affinity/EE checks after preflight and must not be promoted unchanged. Existing M1 artifacts and the boot asset lock are unchanged.

See the [subsequent CPU guard and panic review](p7-entry-cpu-review.md) for updated guard ordering, broader register readbacks and the explicit remaining static-stack gap.
