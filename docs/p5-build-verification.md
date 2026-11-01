# P5 snapshot assembly and manifest publication

Status: M1 Windows `build` implementation, verified on 2026-11-01. P5 is complete within the [M1 acceptance scope](m1-acceptance.md). The later [verifier candidate](p5-verification.md) adds verification/report ingestion using approved profile 0.1.1; the later failure acceptance is documented in the M1 record. This extends the [Windows process foundation](p5-process-verification.md).

## Delivered behavior

`rustos build --repo <directory> --config <file> --format json` validates the configuration and module graph, rejects missing source/lockfile prerequisites and an occupied output destination, then creates an exclusive sibling staging directory. The supported M1 build layout is exactly the four selected kernel/HAL/BSP/console crates; generic source layouts remain inspection-only.

The builder copies the root workspace and lockfile, all files within selected source directories except Cargo caches/Git metadata, configuration, profile, catalog and recipe into a retained source snapshot. It checks inspected input hashes against the captured bytes, re-inspects the captured metadata, checks local dependencies, and holds read locks over snapshot inputs through both builds. Inputs in the manifest use paths relative to the bundle's `source/` directory. Snapshot limits are 4096 files, 16 MiB per file and 64 MiB source-tree data.

Normal and explicit `panic-test` kernels compile separately from that snapshot with Cargo `--locked --offline`. Processes run inside owned Windows jobs with restricted inherited handles and an explicit environment. Ambient Rust flags, compiler wrappers and Cargo profile overrides are excluded. Cargo uses a fresh private home; ancestor Cargo configuration is rejected. Rustup resolves the installed compiler/Cargo executables, whose reported versions are retained in the manifest. The bare-metal target must already be installed. Each tool has a 120-second deadline and 1 MiB retained capture limit per stream. This does not make arbitrary build scripts hermetic or sandbox their filesystem access; the supported repository's build script reads its captured linker/startup inputs.

ELF packaging checks architecture, entry point, program-header bounds, file-backed executable entry, memory range, segment overlap and writable/executable conflicts. Both artifact variants must differ. A schema-1 manifest identifies every captured project input, selected module/reason, tool version, target, recipe and artifact hash/size. A same-volume move publishes the complete directory without replacing a destination. Sources, compile outputs and logs remain inside that bundle; verification must add external reports rather than modify it.

On failure the final output remains absent, existing outputs remain unchanged, and any created staging retains incomplete state plus diagnostics/logs. CLI stdout is a single final JSON record. Build CLI `evidence` paths are relative to the configuration's parent directory; the successful `manifest_path` is absolute. Invalid invocation/metadata returns 2; missing prerequisites/layout/path-length restrictions return 3; build/package errors 4; timeout 6; cancellation 7; cleanup/report failure 8.

Read-only `validate`/`plan` continue to report readiness false with `EXECUTION_PREREQUISITES_UNCHECKED`: they do not launch tool probes. Successful `build` reports readiness true after execution checks and compilation. A passing build does not claim emulator verification.

## Two-pass validation

Nine acceptance cases exercise actual CLI output against the existing JSON schemas, all manifest source/artifact hashes, both ELF variants, occupied-destination preservation, intentional compilation failure, malformed workspace rejection, missing root lockfile/tool prerequisites, dependency escape rejection and excessive Windows output-path depth. The positive build succeeds despite deliberately invalid ambient Rust flags/wrappers/profile settings.

Both packaged artifacts are also independently inspected and booted through the existing P4 development harness. Normal startup emits `RUSTOS_BOOT_OK`; the explicit test kernel emits `RUSTOS_EXPECTED_PANIC`. Each check performs bounded QMP stdio shutdown. This harness is development evidence, not the still-pending production Job Object/named-pipe `verify` command.

First-pass fixes addressed canonical Windows local paths, relative evidence-path schema compliance, explicit UTF-8 compiler-log decoding and long Windows linker paths. The builder now uses shorter internal compilation paths and rejects excessive depth before compilation. Retained historical failed staging is not marked successful. Final acceptance is repeated after those fixes; raw records are linked below when recorded in the dashboard.

Final raw records: [acceptance pass 1](evidence/p5-build-pass1.json) and [acceptance pass 2](evidence/p5-build-pass2.json). The final Rust suite has 29 passing methods, including explicit child-environment isolation; five CLI regression methods also pass. Static validation passes with the same two documented existing P3 lint exclusions as the process foundation.

Reproduce:

```powershell
cargo build --manifest-path tools/assembler/Cargo.toml --locked
python tools/test_assembler_build.py
python tools/test_assembler_cli.py
cargo test --manifest-path tools/assembler/Cargo.toml --locked --features test-fixtures
```

Install [design-test dependencies](../tools/requirements-design.txt) if unavailable in the Python environment. The build acceptance script retains unique directories under `target/`, including its JSON acceptance summary, source snapshots, manifests, kernels and failed staging. No test writes physical media.

## Remaining delivery work

Production verification still needs strict manifest consumption and stable artifact identity, authenticated owned QMP named-pipe control, exact marker/deadline/drain handling, external terminal reports, rejection cases and automatic dashboard ingestion. The initial result is an emulator-loadable ELF bundle, not a Raspberry Pi SD-card image or an ISO. Physical Zero 2 W and Pi 5 delivery remains later work.
