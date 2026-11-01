# RustOS assembler host tool

`validate` and `plan` inspect configuration. Windows `build` compiles the supported M1 source layout from a captured snapshot, producing normal/panic-test ELF kernels and a hashed manifest. Windows `verify` consumes an existing bundle, runs separate bounded scenarios and retains external reports. Approved profile 0.1.1 requires `instruction_counting = "auto"`; older provisional reports keep their historical labels. M1 emulator acceptance is complete; see [delivery evidence](../../docs/m1-acceptance.md).

From the repository root:

```powershell
cargo build --manifest-path tools/assembler/Cargo.toml --locked
cargo run --manifest-path tools/assembler/Cargo.toml --locked -- validate --repo . --config docs/examples/m1.toml
cargo run --manifest-path tools/assembler/Cargo.toml --locked -- plan --repo . --config docs/examples/m1.toml --format json
cargo run --manifest-path tools/assembler/Cargo.toml --locked -- build --repo . --config docs/examples/m1.toml --format json
cargo run --manifest-path tools/assembler/Cargo.toml --locked -- verify --repo . --manifest docs/examples/out/m1/manifest.json --format json
cargo test --manifest-path tools/assembler/Cargo.toml --locked
```

Cargo compiles this host application and can update its own build cache. The compiled CLI's inspection commands do not compile selected OS modules, launch tools, create output directories or modify repository files. For machine integration, call the compiled binary directly: `tools/assembler/target/debug/rustos.exe` on Windows. Cargo's own progress is separate from the CLI's single JSON stdout result.

This crate has its own workspace and lockfile, isolating host inspection from the bare-metal workspace. The checked toolchain is Rust/Cargo 1.88.0 on Windows MSVC. The root OS workspace now builds the P4 minimal emulator kernel.

## Behavior

- Strict typed TOML parsing, version/unknown-field/type checks, and identifier validation.
- Explicit repository profile/catalog/recipe discovery; no network or ancestor-catalog search.
- Full catalog dependency checks; selected module compatibility and conflicts; deterministic dependency-first ordering and all direct selection reasons.
- Input byte hashes, versioned recipe identity, source-layout/readability checks and explicit missing-prerequisite warnings.
- Safe relative paths, checks for existing symlink/reparse components, and rejection of output overlap with sources, metadata, configuration inputs and host-tool code.
- Exit 0 means inspection succeeded; exit 2 means invalid invocation/configuration/metadata or unreadable inspection inputs. It does not imply a successful OS build. Future execution-stage exit codes remain outside P3.

Read-only inspection reports readiness false with `EXECUTION_PREREQUISITES_UNCHECKED`, because source presence does not prove toolchain or compilation readiness. Successful build reports readiness true after execution checks. Default `Cargo.toml` plus `src/lib.rs`/`src/main.rs` layout is inspected; build currently supports exactly the four approved M1 source crates. No source is executed by inspection.

Build output resolves relative to the configuration file, and existing destinations are never replaced. The bare-metal target must already be installed; build runs offline without installing prerequisites. Manifest inputs refer to paths within bundle `source/`. Failure CLI evidence paths are relative to the configuration directory; successful manifest paths are absolute. See [snapshot build behavior and limits](../../docs/p5-build-verification.md).

## Acceptance checks

Rust integration tests cover graph, schema, path, recipe and CLI behavior. Independent Python black-box tests consume the documented fixture list, validate actual CLI records against the design contracts, compare input hashes, and check that inspection leaves its fixture tree unchanged:

```powershell
python -m pip install -r tools/requirements-design.txt
python tools/test_assembler_cli.py
python tools/test_assembler_build.py
python tools/test_assembler_verify.py
cargo test --manifest-path tools/assembler/Cargo.toml --locked --features test-fixtures
```

## Limits

Filesystem identity checks reject detected links/reparse points but do not provide atomic handle-based protection against every concurrent directory replacement. Build connects Windows jobs, bounded supervision, stable snapshot reads and no-replacement publication. Arbitrary build scripts are not hermetic. The verifier candidate adds owned PID-checked QMP control, external reports and automatic terminal-outcome dashboard ingestion. Cancellation and report/cleanup failure acceptance is complete within M1; in-flight command streaming remains a follow-up improvement. The `test-fixtures` feature enables an integration-test helper; acceptance retains unique output under `target/`. See [P3 evidence](../../docs/p3-verification.md), [P5 foundation evidence](../../docs/p5-process-verification.md), [P5 build evidence](../../docs/p5-build-verification.md) and [verifier evidence and proposal](../../docs/p5-verification.md).
