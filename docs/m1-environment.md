# M1 environment investigation

Status: environment direction agreed and environment probes passed on 2026-10-31. See [recorded verification](m1-environment-verification.md) for installed versions, invocation, evidence and limits. RustOS build/boot verification remains pending. The proposal and alternatives below preserve the selection rationale; the verification record supersedes the original installation observations.

## Observed local environment

- Windows host; Rust and Cargo 1.88.0 are available.
- Active host toolchain is `stable-x86_64-pc-windows-msvc`.
- `aarch64-unknown-none-softfloat` is installed alongside the host target.
- QEMU is absent from PATH and two common installation locations checked. This does not prove it is absent everywhere.
- WSL lists only `docker-desktop`, version 2, stopped. No general-purpose Linux development distribution was listed.

## Recommended initial profile

| Item | Proposal | Rationale |
| --- | --- | --- |
| Development host | Native Windows for M1 | Reuse the installed Rust toolchain and avoid requiring a new Linux distribution for initial boot work |
| Emulator | QEMU system emulation | Explicit machine/CPU selection and serial output suitable for bounded automated tests |
| Machine | `virt`, with a versioned machine selected after installation | A generic virtual platform with a documented device model; pin release and machine version for repeatability |
| CPU | `cortex-a53`, one emulated core | Explicit AArch64 CPU supported by virt; multicore remains outside M1 |
| Rust target | `aarch64-unknown-none-softfloat` | Already installed; bare-metal no_std target avoids a hard-float calling convention during early kernel work |
| Console | Polling PL011 serial | Present in the virt device model; device addresses and startup contract must be defined for this profile |
| Verification | Separate startup and deliberate-panic scenarios | Capture serial output; use explicit expected markers and bounded execution; retain separate results |

The installed Rust version is a candidate, not yet a tested or agreed toolchain pin. A successful kernel build must establish compatibility before pinning it. QEMU release, RAM size, memory map, entry conditions, artifact loading mode, startup markers, and timeout values remain design work. The soft-float ABI does not eliminate the need to review generated instructions and CPU state assumptions.

## Alternatives considered

1. Raspberry Pi machine emulation: official QEMU documentation lists several Raspberry Pi machines, but does not list an exact Zero 2 W or Pi 5 model. Do not equate another board model with either physical target.
2. Linux development under WSL: useful for future Raspberry Pi ELF/firmware research, but requires a general-purpose distribution and Linux tool setup. It remains separate work; Docker's internal distribution is not selected as our development environment.
3. Generic virt emulator: recommended for M1's portable kernel and assembler verification. It cannot validate Raspberry Pi firmware, board addresses, or real peripheral behavior.

## Proposed verification contract

The minimal profile must produce an emulator-loadable kernel and component manifest. A test runner launches only its owned QEMU process, captures output, checks startup and panic markers in separate scenarios, and settles the process on success, failure, cancellation or timeout. Deliberate panic is a successful scenario only when the expected marker and stopping policy match. Exact executable commands will be documented once loader and linker contracts are established.

## Remaining P1 exit work

P1 environment selection and probes are complete; the following original checklist is superseded by the verification record. Concrete kernel/startup interface details continue in P2 and later implementation tasks.

- Agree on native Windows plus QEMU virt as the first profile.
- Install or locate a suitable QEMU build and record its provenance/version.
- Check the actual machine/CPU inventory, choose a versioned machine, and record an invocation.
- Confirm Rust toolchain/target suitability for the proposed startup design.
- Specify loader/entry assumptions and bounded verification behavior for the schema/design work that follows.

## Primary sources

- [QEMU virt machine](https://www.qemu.org/docs/master/system/arm/virt.html): supported CPU choices, PL011 console, and versioned machine behavior.
- [QEMU Raspberry Pi machines](https://www.qemu.org/docs/master/system/arm/raspi.html): listed board models and peripheral coverage.
- [Rust bare-metal AArch64 targets](https://doc.rust-lang.org/rustc/platform-support/aarch64-unknown-none.html): target ABI, core/alloc support, linking, and requirement for a supplied linker script.

The QEMU sources are development documentation; actual installed-version capabilities must be checked before recording a supported profile.
