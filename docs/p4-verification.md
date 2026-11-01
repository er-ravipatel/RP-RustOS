# P4 kernel implementation and emulator evidence — 2026-11-01

## Outcome and scope

RustOS now boots a minimal Rust kernel in the selected QEMU environment. P4 implements the emulator BSP configuration, polling PL011 transmit driver, console contract, AArch64 entry/linker/vector setup, initialization sentinels, panic path and negative test variants. This is not yet an assembled release image, Raspberry Pi port, shell or scheduler.

## Two-pass review and corrections

Codex performed implementation self-review. Pass 1 built normal, deliberate-panic and BRK exception variants and checked the unsupported-entry negative scenario. All passed. Pass 2 corrected the BSP/driver boundary, strengthened stack-bound and VBAR identity checks, poisoned the actual BSS sentinel before clearing it, and added explicit unexpected-panic rejection. A final run used warning-free kernel builds and complete-line marker matching. ELF inspection independently checked addresses, flags, non-overlap, vector/stack placement and recorded hashes.

The root Cargo workspace now lists only its four implemented target crates: kernel, HAL, QEMU BSP and console driver. Planned component directories are not fabricated as buildable packages. The host assembler remains its own workspace. The kernel explicitly enables FP/SIMD access before Rust; the soft-float ABI is not treated as proof that the compiler never emits those instructions.

## Final recorded results

| Check | Observed outcome |
| --- | --- |
| Normal kernel | Initialization diagnostics followed by exact `RUSTOS_BOOT_OK` line |
| Deliberate panic | Armed internal test reached the Rust panic handler and emitted `RUSTOS_EXPECTED_PANIC` |
| Injected BRK | Exception diagnostics with ESR `0xf2000000`, ELR and FAR; no success/panic marker |
| Unexpected panic | `RUSTOS_UNEXPECTED_PANIC`; never accepted as the deliberate-panic scenario |
| Unsupported entry profile | No startup success/serial output during the bounded observation; owned QMP shutdown succeeded |

The last check observes rejection under changed virtualization settings; silence alone is not a diagnostic proof of the precise instruction at which execution stopped.

All five checks passed their expected behavior. All QEMU processes settled through QMP quit without forced termination. Normal and panic checks observed their complete final lines within the configured ten-second marker budget. The unsupported-entry rejection used a two-second negative observation window, separate from production startup verification.

Raw records: [pass 1](evidence/p4-pass1.json), [pass 2](evidence/p4-pass2.json), and [final evidence](evidence/p4-final.json). Historical artifact hashes in early-pass records identify those earlier builds; final evidence matches the final artifacts. The evidence is P4 development data, not the proposed assembler verification-report schema.

## Reproduce

From the repository root:

```powershell
python tools/test_kernel.py --report target/p4/new-evidence.json
python tools/test_kernel_protocol.py
```

The report path must not already exist. The harness builds four variants using the recorded compiler and root lockfile, checks the ELF files, runs QEMU and writes explicit evidence. It never writes physical media. Use `--qemu` to override the executable path. The checked environment is Rust/Cargo 1.88.0 and QEMU 11.1.0 with virt-11.1/Cortex-A53/one core/128 MiB/TCG.

The target output is ELF, with entry `0x40080000`, vector table at a 2048-byte-aligned address, separate loadable text/rodata/data ranges, a 64 KiB stack, and a link-time upper limit of `0x40200000`. ELF segment flags describe layout, not active MMU permission enforcement. Runtime checks established EL1, expected disabled MMU/cache bits, data preservation, BSS clearing, stack bounds/alignment and the installed vector address before the success marker.

## Regression coverage

Seventeen Rust host-inspector tests, five independent CLI test methods, twelve contract tests, eight tracking tests, and three marker-protocol test methods passed in addition to the five final emulator checks. Protocol tests reject unterminated/prefixed markers, fault markers that accompany success, over-limit lines/streams and invalid UTF-8. Source code and limits still need production verifier integration tests in P5.

## Important delivery boundary

The harness uses an owned QMP stdio channel with serial captured separately in a temporary file. It retains a direct process handle and tests clean shutdown; it does not implement the approved production named-pipe/Windows Job Object process-tree lifecycle. That is P5 work, along with snapshots, manifests, no-replacement bundle publication, strict build/verify CLI integration and automatic dashboard ingestion. It does not prove process-tree containment, timing under all host loads, long-term stability or hardware compatibility.

P4 is complete for the scoped emulator startup slice. Full M1 remains in progress until the assembler can produce and verify the artifacts end to end. Zero 2 W and Pi 5 images remain unimplemented.
