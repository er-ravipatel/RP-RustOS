# Strict design schemas

M2 input design contracts are separate: [m2-inputs.schema.json](m2-inputs.schema.json) and [verification scope/limits](../m2-input-contract-verification.md). They do not enable Pi support in the assembler or weaken the schema-1 M1 contracts below.

M2 manifest and image/hardware report contracts are in [m2-outputs.schema.json](m2-outputs.schema.json), with [semantic checks and limits](../m2-output-contract-verification.md). The generated schema is structural; use the semantic utility for cross-record checks. Synthetic fixtures are never published as execution records.

Hardware-session and completed-verification index contracts are in [m2-sessions.schema.json](m2-sessions.schema.json), with [syntax fixtures and remaining failure-envelope gaps](../m2-session-contract-verification.md).

Terminal failures and report recovery are now defined separately in [m2-failures.schema.json](m2-failures.schema.json), with [checked failure cases and remaining runtime limits](../m2-failure-contract-verification.md).

[contracts.schema.json](contracts.schema.json) contains named Draft 2020-12 definitions for parsed user TOML (`config`), target profiles (`profile`), module metadata (`catalog`), resolved plans (`plan`), bundle manifests (`manifest`), verification reports (`verification`), and CLI results (`cli`). Select the corresponding `$defs` entry when validating; the root is a definition container, not a validator for arbitrary records.

Generate with `python tools/build_contract_schemas.py`. Check with `python tools/check_design_contracts.py` and `python tools/test_design_contracts.py`. Install the optional design-test dependencies from [requirements-design.txt](../../tools/requirements-design.txt) into a virtual environment first. Python 3.11 includes TOML parsing; Python 3.10 uses tomli (the test utility also permits pip's bundled parser as a local fallback).

The checker adds cross-field checks for duplicate IDs, artifact variants, timestamp order, required scenarios, final states, marker identity, cleanup, evidence presence, and report-to-manifest artifact binding. Synthetic fixtures exercise rejection paths. They are not real successful runs and are never inserted into the dashboard run list.

Limits: these tools do not implement dependency resolution, load executable plugins, build sources, prove artifact bytes match a hash, validate a live filesystem path, establish process ownership or run a kernel. Unknown target/feature lookups, graph cycles/conflicts, source readiness, actual hashes and publication races require their implementation checks. Lexical path constraints supplement rather than replace filesystem identity checks. The schema currently constrains the selected M1 emulator; adding a target requires an explicit schema/profile extension.

Two passes: structural validation and negative fixtures first; independent cross-record cases (wrong artifact identity, duplicate variants, nested false CLI success, wrong operation result) second. Detailed validation results are design evidence, not delivered OS verification.
