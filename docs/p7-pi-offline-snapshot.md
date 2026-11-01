# P7 Pi isolated offline compilation acceptance

2026-11-01. An explicitly invoked engineering acceptance test in [pi_build.rs](../tools/assembler/src/pi_build.rs) compiles both reviewed Pi variants from a new source snapshot. This is test scaffolding, not an enabled production Pi build backend.

The test reuses the existing bounded snapshot and owned-process helpers. It copies the three deduplicated roots from the typed Pi plan, excludes nested target and Git directories, retains per-file SHA-256, and omits the root M1 workspace manifest. The Pi kernel keeps its own lockfile and workspace. Ancestor Cargo configuration is rejected; a fresh Cargo home and the existing environment whitelist isolate execution from ambient Cargo flags and cached dependencies.

For each variant, locked/offline Cargo metadata must report exactly four local packages with canonical manifest paths inside the snapshot. Separate target directories prevent normal/panic artifact replacement. Both release builds use aarch64-unknown-none-softfloat; normal has no extra features and panic-test enables only panic-test. The test checks ELF magic, retains distinct ELF hashes, and verifies every recorded snapshot file hash again after compilation. It records verbose Cargo/rustc identity, commands, owned process IDs, metadata and bounded logs. It does not make the snapshot read-only or prove the absence of additional generated files.

## Results

[Retained evidence](evidence/p7-pi-offline-snapshot.json) records successful normal and panic compilation, four-package closure, exact source hashes and compiler identities. Full logs and binaries remain under the report's test-owned output directory. Repeat with:

```powershell
cargo test --manifest-path tools/assembler/Cargo.toml isolated_offline_pi_variants -- --ignored --nocapture
```

The explicit cross-compilation acceptance passes separately from the 38 regular Rust assembler tests. Five M1 CLI and nine M1 build acceptance tests pass, including independent emulator boot. Scoped all-target Clippy passes with warnings denied except the previously recorded result_large_err allowance.

First self-review checked snapshot ownership, fresh Cargo home, exact local package closure and per-variant directories. Second self-review checked unchanged source hashes, distinct artifact identity, bounded process reuse and continued public backend gating.

## Remaining work

Move the proven path into a production Pi snapshot/compiler component with structured failures and negative acceptance cases. Revalidate linker, entry, stack and feature contracts against those exact output ELFs. Then implement flat kernels, locked firmware/source notices, both complete SD images and independent inspection before enabling schema-2 publication. No complete image, physical boot claim or media write is produced by this test.
