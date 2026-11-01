# Report and manifest contract — schema 1 proposal

Status: two-pass reviewed report/manifest contract approved by the user as an implementation baseline on 2026-10-31. The assembler produces inspection/build CLI records and complete M1 bundle manifests. The [verifier candidate](p5-verification.md) also produces external terminal reports; it uses the approved emulator profile 0.1.1. JSON is used for machine-readable results; configuration remains TOML.

## Shared conventions

Require `schema_version = 1`, reject unknown fields, and reject wrong types. IDs are nonempty strings; SHA-256 values are 64 lowercase hexadecimal characters; timestamps are UTC RFC3339 strings. Artifact paths use relative `/` separators inside the bundle. Evidence paths are relative to their containing report directory and must not escape it; the dashboard importer maps those records into its own validated repository-relative references. Hashes identify bytes, not trust or authenticity.

State fields use `not_run`, `running`, `passed`, `failed`, `cancelled`, `timed_out`, or `skipped`. `running` is allowed only in explicitly incomplete progress records. A final operation result must use a terminal outcome. Unknown/incomplete states never imply success.

## CLI result

Exact fields: `schema_version`, `operation`, `status`, `target`, `build_ready`, `diagnostics`, `result`, `evidence`.

- `operation`: validate, plan, build, or verify.
- `target`: selected ID, or null when parsing/selection failed.
- `build_ready`: boolean for validate/plan/build, null for verify or when readiness cannot be established.
- `diagnostics`: array of `{code, severity, stage, message, input, field, dependency_chain}`. Severity is error/warning/info; input and field are string or null; chain is an array of IDs. Empty chains are permitted.
- `evidence`: array of paths to retained run diagnostics, empty when inspection creates no files.
- `result`: an operation-specific object, or null when the operation could not produce its result.

In JSON mode stdout is one final result. Progress and child logs must not contaminate it. Exit-code categories follow the [CLI proposal](cli-design.md); their numeric values remain a separate CLI detail pending final schema reconciliation.

## Plan result

Fields: `requested_features` (distinct IDs), `resolved_modules` (array), `build_order` (distinct module IDs), `inputs` (array), `artifact_format`, `verification_recipe`, `missing_prerequisites` (diagnostic array).

Each resolved module is `{id, version, reasons}`; reasons are objects `{kind, from}` where kind is base/feature/dependency and from is the corresponding target/feature/module ID. Preserve all direct reasons. `build_order` contains every selected module exactly once, after its dependencies. Inputs contain `{path, sha256}` for the bytes actually parsed. Declared versions do not substitute for input hashes. Plan inspection may pass with readiness false; unknown modules and cycles remain errors.

## Complete bundle manifest

Fields: `schema_version`, `bundle_id`, `created_at`, `complete`, `target`, `requested_features`, `resolved_modules`, `inputs`, `tools`, `artifacts`, `verification_recipe`.

- `complete`: true only after packaging checks; incomplete staging is not a consumable bundle.
- `target`: `{id, version, architecture, rust_target}`.
- `inputs`: `{path, sha256}` entries identifying configuration, profile, catalog and each selected source input. Capture all consumed files or reject changes during the build; a precise snapshot mechanism remains implementation work.
- `tools`: `{name, version}` entries, including Rust and any required packaging tools.
- `artifacts`: exactly the normal and deliberate-panic ELF records for this M1 recipe, each `{id, variant, path, sha256, size_bytes}`. IDs/paths must be unique. Variants are normal/panic-test. Size is a nonnegative integer. Both variants derive from the same identified source snapshot with the explicit test-variant selection recorded in `variant`.
- `verification_recipe`: `{id, version, sha256}` identifying a trusted repository recipe, not executable commands embedded in the manifest.

No verification pass is embedded in an immutable build manifest. Hashes are checked against stable opened/copied inputs at consumption; hashing and reopening an arbitrarily changed file is not sufficient identity protection. Recompute the manifest hash when binding a verification report; the manifest does not contain its own hash.

## Verification report

Fields: `schema_version`, `run_id`, `complete`, `operation`, `target`, `manifest_sha256`, `verification_scope`, `started_at`, `finished_at`, `status`, `steps`, `cleanup`, `diagnostics`, `evidence`.

- `operation`: verify. `verification_scope`: emulator for M1; hardware is a separate supported verification method, never inferred.
- `complete`: false for progress; true means final reporting finished, even when the run failed.
- `finished_at`: null while running, timestamp for a complete record. It must not precede start.
- Each step is `{id, artifact_id, artifact_sha256, status, deadline_ms, observed_marker, stop_requested, logs, diagnostics}`. Scenario IDs are startup/panic; deadline is initially 10000. Marker is exact captured line or null. Logs are `{stream, path, sha256}` with stream stdout/stderr.
- `cleanup`: `{status, stop_budget_ms, kill_budget_ms, processes_settled, diagnostics}`. Status is not_run/running/passed/failed; processes_settled is boolean; both budgets are initially 5000.
- A passing final report requires both distinct scenarios passed, exact matching artifact identities and expected markers, stop_requested true, cleanup passed with processes_settled true, and no error diagnostics. An absent or skipped scenario prevents success. Child termination code caused by the runner is recorded in diagnostics or logs and is not automatically a guest crash.
- Reporting or cleanup failure prevents a passed final result. A complete failed report remains useful evidence; an incomplete one is explicitly unresolved.

## Publication layout

Proposed names: sibling `.rustos-staging-<run-id>/` for assembly, configured final bundle directory containing `manifest.json` and two ELF artifacts, and sibling `.rustos-reports/<bundle-id>/<run-id>/` containing verification logs/report. Use exclusive creation for run IDs and same-volume no-replacement publication. Never treat a hidden directory name as a security guarantee. Failed staging is retained with explicit incomplete state. Reports finalize through a temporary file and a no-replacement rename inside their own unique directory.

## Two checks and remaining implementation proof

Pass 1 checked field roles against CLI/configuration separation and the confirmed immutable-bundle policy. Pass 2 walked missing artifacts, duplicate scenarios, wrong hashes, timeout, failed cleanup, skipped verification and incomplete-report cases: none may produce verified success. This is contract analysis, not execution of a JSON Schema validator or runtime reporting implementation. Concrete strict schemas and executable rejection fixtures must be added in P3/P5. The existing dashboard run model needs an explicit importer mapping; it is not silently interchangeable with this proposed report.
