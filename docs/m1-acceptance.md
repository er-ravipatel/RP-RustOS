# M1 acceptance: minimal assembler and emulator boot

Outcome: the scoped M1 exit criteria are met on 2026-11-01. This is the Windows/QEMU emulator milestone. Zero 2 W SD-card images, Pi 5 images and the later OS subsystems remain separate work.

## Delivered result

The root [configuration](../rustos.toml) selects the approved QEMU profile 0.1.1, HAL, BSP, PL011 console and kernel. The delivered bundle is `out/m1/`, containing `manifest.json`, `kernel.elf`, `kernel-panic-test.elf`, the identified source snapshot and build logs. Manifest SHA-256: `11aa1d74b1edcb082d8772239b14885890a66bbc0a2ed401ddd0b94b0b706c97`.

The [delivery build record](evidence/m1-delivery-build.json) records compilation and packaging passed and verification not run by the build command. The separate [delivery verification record](evidence/m1-delivery-verify.json) records both exact markers, requested owned shutdown and settled cleanup. The complete bundle was hashed before and after verification and remained unchanged.

Environment: Windows MSVC; Rust/Cargo 1.88.0; installed `aarch64-unknown-none-softfloat`; QEMU 11.1.0, `virt-11.1`, Cortex-A53, one core, 128 MiB, TCG, secure off, virtualization off, GICv2, approved `-icount shift=auto`. M1 reproducibility means repeatable artifact type and behavior with identified inputs; byte-identical builds are not claimed.

## Reproduce

```powershell
cargo build --manifest-path tools/assembler/Cargo.toml --locked
tools/assembler/target/debug/rustos.exe validate --repo . --config rustos.toml --format json
tools/assembler/target/debug/rustos.exe plan --repo . --config rustos.toml --format json
tools/assembler/target/debug/rustos.exe build --repo . --config rustos.toml --format json
tools/assembler/target/debug/rustos.exe verify --repo . --manifest out/m1/manifest.json --format json
```

The delivered output already exists, so a second build rejects it by design. Verify it directly, or choose a fresh relative output path in a separate configuration for another build. Never edit or overwrite a bundle to upgrade it. The output is emulator-loadable ELF; physical media is never written by these commands.

## Requirement evidence

| Requirements | Observed acceptance | Evidence |
| --- | --- | --- |
| ASM-001/002/003/004 | Strict configuration, graph compatibility and dependency reasons; deterministic read-only inspection; invalid fixtures and missing sources/tools/lockfile rejected | [Inspector](p3-verification.md), [build](p5-build-verification.md), Rust inspector tests and CLI/build acceptance |
| ASM-005/006 | Both variants compile offline from one captured source set; manifest input, module, tool and artifact identities match | [Build evidence](p5-build-verification.md), [delivered build](evidence/m1-delivery-build.json) |
| ASM-007/012 | Occupied outputs preserved; source snapshots locked; compilation/cancellation leaves incomplete staging; downstream packaging skipped; no failed output published as complete | Build acceptance and [failure pass 1](evidence/p5-failures-pass1.json), [pass 2](evidence/p5-failures-pass2.json) |
| ASM-008/009/013 | Normal and panic scenarios use separate identified artifacts; exact markers, bounds, skipped dependent work and distinct build/package/verification outcomes | [Verifier](p5-verification.md), [delivered verification](evidence/m1-delivery-verify.json) |
| ASM-014 | Real Ctrl+C cancels an active compiler/build-script tree; real Ctrl+C/Ctrl+Break cancels verification; timeout, unexpected QEMU exit and unconfirmed cleanup cannot pass | Failure acceptance below and native owned-process tests |
| ASM-015 | Explicit terminal records are ingested automatically; target/artifact, outcome, captured marker/log identities and cleanup are checked; incomplete report evidence remains accessible | Dashboard importer and localhost HTTP tests; [dashboard instructions](dashboard/README.md) |

ASM-010/011 remain M2. Later feature outlines remain drafts; M1 completion does not mark them implemented.

## Failure acceptance and actual limits

The final eight-case suite passed twice: [pass 1](evidence/p5-failures-pass1.json), [pass 2](evidence/p5-failures-pass2.json). It covers:

1. Actual Ctrl+C during a delayed build script, confirming both Cargo and script process handles signal termination and no final bundle is published.
2. Actual Ctrl+C and Ctrl+Break through an isolated hidden Windows console, confirming cancellation, skipped panic work and QEMU settlement.
3. Unexpected termination of the exact owned QEMU handle, requiring a failed result.
4. A real filesystem collision at the final report temporary path. The operation returns reporting failure, retains an incomplete failure record plus a recovery wrapper containing the original timed-out evaluation and its cleanup result, and never publishes a canonical passing report.
5. A blocked execution-index path, requiring final CLI failure even when the separate guest report truthfully records passing checks.
6. Test-only unavailable cleanup confirmation after real cleanup, requiring exit 8 and failed cleanup. The production binary ignores the same injection variable and passes its positive control.

The console helper verifies that only itself and its owned CLI share the private console before broadcasting. It does not send signals to the user's console. See [Microsoft's console-event contract](https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent). Both build and guest process handles are checked rather than searching/killing by executable name.

Cleanup failure injection is compiled only with the explicit `fault-injection` feature, in a dedicated `rustos-fault-fixture` binary and separate Cargo target directory. It does not disable real cleanup or demonstrate that Windows actually refused process termination; it demonstrates fail-closed reporting when settlement cannot be confirmed. The dashboard labels those reports as fault fixtures.

A report-write failure originally discarded the attempted terminal result. That finding is fixed: `report-recovery.json` retains the original scenario outcomes inside an explicitly incomplete wrapper, and CLI failure evidence records the reporting error. A successful guest check cannot hide report/index failure. OS shutdown or loss of all writable storage can still prevent durable reporting; no guarantee of reporting after abrupt host termination is claimed.

## Verification inventory and review

| Suite | Passing methods |
| --- | ---: |
| Rust inspector, protocol and native process tests | 34 |
| Design contracts | 12 |
| CLI acceptance | 5 |
| Build acceptance | 9 |
| Production verifier acceptance | 8 |
| Console/reporting/cleanup failure acceptance | 8, repeated twice |
| Dashboard tracking/importer/HTTP tests | 25 |

The verifier's existing acceptance suite was rerun after the recovery change. Clippy passed for normal and fault-fixture builds, with the two pre-existing P3 lint exclusions documented in [process evidence](p5-process-verification.md).

Reviewer: Codex, implementation self-review, 2026-11-01. Reviewed against the agreed [M1 outcome](product-direction.md), schema-1 records, profile 0.1.1 and immutable/publication rules. Findings: preserve attempted results after report failure; isolate cancellation broadcasts; distinguish injected observations from real process cleanup; explicitly report unrequested verification; reject overlapping Windows dashboard listeners. All were addressed and exercised. Disposition: accept the scoped M1 implementation and verification stages. This is not an independent review or approval of physical-board compatibility.

Dashboard terminal outcomes refresh every five seconds. In-flight command streaming, browser visual QA, CI automation and support beyond this recorded host remain follow-up improvements, not evidence inferred from these tests. The broader OS implementation and physical-board acceptance remain open.

## Run failure acceptance again

```powershell
cargo build --manifest-path tools/assembler/Cargo.toml --locked
cargo build --manifest-path tools/assembler/Cargo.toml --locked --features fault-injection --bin rustos-fault-fixture --target-dir target/fault-host
python tools/test_assembler_failures.py
```

Use the [design-test Python dependencies](../tools/requirements-design.txt). Finish Cargo builds before running CLI acceptance on Windows: a running executable cannot be replaced by another Cargo build. Test directories and incomplete staging are retained under `target/` for review.
