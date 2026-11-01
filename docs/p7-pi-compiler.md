# P7 internal Pi snapshot/compiler

2026-11-01. The [Pi builder](../tools/assembler/src/pi_build.rs) now contains a reusable compile_snapshot component rather than test-only compilation orchestration. The public CLI remains gated pending complete image publication.

The component returns the existing structured build failures, reuses bounded snapshot/process helpers, rejects output/source overlap before creating output, and refuses an existing output directory. It checks the copied lockfile, rejects ancestor Cargo configuration, uses a fresh Cargo home and locked/offline commands, validates the four-package local closure, and keeps variant output directories separate. Source hashes are rechecked after compilation; identical normal/panic ELF hashes reject. A report is written only after both variants succeed. Failed run directories and tool logs remain available; they do not represent a completed bundle.

[Evidence](evidence/p7-pi-compiler.json) records the actual internal component's successful two-variant build. Its acceptance test also checks output overlap rejection and a second invocation refusing the existing directory. A regular unit test rejects missing/malformed package arrays, duplicate names, registry sources and canonical manifest paths outside the snapshot.

39 regular Rust assembler tests, the explicitly invoked cross-compilation acceptance, five M1 CLI tests and nine M1 build acceptance tests pass. All-target Clippy passes with warnings denied except the previously recorded result_large_err allowance. The original M1 bundle is unchanged.

First self-review checked the extraction's structured errors, command isolation and variant separation. Second self-review checked dependency rejection, output overlap/no replacement and that the pending public backend cannot expose these engineering artifacts as a complete bundle.

This is an internal component reserved for later complete-bundle orchestration, currently exercised by acceptance tests. It has no new public partial-build command. Its output check currently establishes ELF magic and distinct artifact hashes; exact linker/load/stack/entry contracts remain the next task. Snapshot files are hash-checked rather than made read-only. Source stability against concurrent edits, generated extra files, hostile build scripts, toolchain integrity and physical firmware behavior are not proved by this slice.
