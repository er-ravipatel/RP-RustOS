# Assembler CLI and result contract

## Agreed operations

Agreed in the project discussion on 2026-10-31: `validate`, `plan`, `build`, and `verify`. `rustos` now implements inspection plus the Windows M1 build path; production verify remains pending. The detailed baseline below describes the full interface. See [current build behavior](p5-build-verification.md), including explicit `--repo`, implemented exit codes and evidence-path resolution.

```text
rustos validate --config <file> [--format text|json]
rustos plan     --config <file> [--format text|json]
rustos build    --config <file> [--format text|json]
rustos verify   --manifest <file> [--format text|json]
```

The initial commands use repository-local target profiles and module metadata. Catalog discovery rules must be fixed before implementation; user-supplied paths must not select arbitrary executable commands. A common internal loader/resolver serves all four operations.

## Operation boundaries

| Operation | Checks and effects | Success means |
| --- | --- | --- |
| `validate` | Parse TOML; validate fields, target and features; resolve compatibility/dependencies; inspect source prerequisites; do not compile, execute a guest, or create output directories | Configuration and metadata are semantically consistent; return `build_ready` separately |
| `plan` | Same input checks; emit requested features, resolved module versions, reasons, deterministic ordering, input identities, target constraints and missing prerequisites; no compilation or OS output | A coherent plan was produced; missing sources remain explicit in `build_ready = false` |
| `build` | Revalidate and resolve; require source/tool prerequisites; reserve an unused destination; compile in an isolated run directory; inspect/package artifacts and manifest | Complete artifact bundle exists and hashes match; verification is `not_run` |
| `verify` | Read a complete bundle manifest; validate artifact hashes and target/recipe identity; require verifier prerequisites; run bounded startup and panic scenarios using those exact artifacts | Both requested scenarios pass and owned processes settle; emulator scope explicitly recorded |

`validate` and `plan` can succeed for coherent planned module metadata with missing source files. Unknown modules, conflicts and cycles fail both operations. A missing source/tool prerequisite prevents `build` or `verify` and yields nonzero. A valid future hardware profile does not become supported by merely naming it.

`verify` never recompiles or repackages. A changed/missing artifact or unsupported recipe fails before guest launch. A future combined build-and-verify operation can compose these commands; there is no implicit verification in `build`. Separate invocations must preserve the identity of the bundle being checked.

## Output and errors

Default format is concise text. In JSON mode, stdout contains exactly one final result object; progress and child-tool logs go to stderr or retained log files, never mixed into stdout. Use argument arrays to start tools, not shell interpolation. Human diagnostics must identify the failed stage and reason without claiming an image is verified because it compiled.

Proposed common result envelope:

```json
{
  "schema_version": 1,
  "operation": "plan",
  "status": "passed",
  "target": "qemu-virt-a53",
  "build_ready": false,
  "diagnostics": [],
  "result": {},
  "evidence": []
}
```

Operation status describes the requested operation. A passed metadata inspection is not a passed build/test. `build_ready` is relevant to validation/planning/build and is null for verification. A failed result includes a diagnostic with `code`, `stage`, `message`, `input`, and optional `field` or `dependency_chain`. Diagnostics distinguish fatal errors from readiness warnings using a required `severity` field. Requested and resolved module identities belong in the plan result, not this illustrative empty object.

Proposed exit codes: `0` successful requested operation, `2` invalid invocation/configuration/metadata, `3` missing prerequisite or invalid artifact identity, `4` compilation or packaging failure, `5` requested verification failed, `6` operation deadline exceeded, `7` cancellation, and `8` reporting/cleanup failure. If cleanup fails after another failure, retain both diagnoses and use code 8. Platform shutdown may prevent a final report; do not claim guaranteed reporting after abrupt termination.

## Artifact bundle and verification reports

Build creates a complete bundle manifest only after packaging checks succeed. It records schema version, target/profile version, requested features, resolved modules and reasons, source identities, tool versions, artifact-relative paths/hashes, and verification recipe identity. Verify rejects paths outside the bundle and checks the manifest against the installed trusted recipe rather than treating manifest content as executable instructions.

Never overwrite a previous successful bundle or mutate its artifacts to attach test results. Each verification attempt creates a unique report directory beside the bundle, with `run_id`, manifest hash, artifact hashes, target, scope, timestamps, step results, process cleanup state and log/evidence paths. The precise directory names and atomic final-report mechanism remain pending design. Failed or cancelled attempts retain identifiable reports and available diagnostics; incomplete reports must be recognizable.

The dashboard integration consumes explicit reports, with paths and outcome validation. Publishing reports automatically to the dashboard is not implemented. Plan/validate inspection results and synthetic environment probes do not populate the assembler build-run list as delivered OS runs.

## Confirmed verification and publication policy

Startup and deliberate-panic checks are separate scenarios, each bounded by its own declared deadline. Missing expected output, unexpected exit/panic, timeout or failed owned-process cleanup prevents verification success. Timeout in the synthetic environment probe is not the default production recipe: the real recipe must define success termination explicitly. The user confirmed separate normal and panic-test artifacts, exact final markers, a ten-second marker deadline, owned-process stop/drain/settlement, and same-volume no-replacement publication. See the [confirmed two-pass review](verification-publication-review.md) for details. Concrete kernel initialization, process ownership, report schemas and implementation remain pending.

## Acceptance scenarios

1. Invalid TOML or an unknown feature: nonzero and structured diagnostic; no compilation or guest launch.
2. Valid metadata with missing crates: validate/plan succeed, report readiness false and missing paths; build fails before compilation.
3. A plan inspection leaves output directories untouched, even when the configured destination already exists.
4. Build to an occupied destination fails without altering prior outputs.
5. JSON stdout parses as one result object even when a child tool writes verbose logs.
6. Verify altered artifacts: nonzero identity error before QEMU starts.
7. Build success followed by failed verification: bundle remains intact; a separate failed report preserves exact artifact identity.
8. Cancellation, deadline or cleanup failure returns its distinct outcome and retained step diagnostics when reporting is possible.

Map these scenarios to ASM-001 through ASM-015 during P3. Detailed report schemas, CLI spelling and exit-code policy need review; operation selection alone does not approve every proposed field.
