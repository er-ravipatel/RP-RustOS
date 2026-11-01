# M2 terminal-failure and recovery contract checks

2026-11-01. [Generated failure schemas](schemas/m2-failures.schema.json), [semantic validation](../tools/m2_failure_contracts.py) and [synthetic tests](../tools/test_m2_failure_contracts.py). No runtime publisher/importer or Pi backend was enabled.

Records distinguish a terminal operation (`terminal=true`) from a completed consumable deliverable (`complete=false`). Separate closed kinds cover preflight rejection, failed builds and verification-report publication recovery. None permits status passed. A failed build records the first unsuccessful stage and skips subsequent stages. Preflight cannot claim acquired runtime resources. Cleanup observations remain explicit, including unconfirmed ownership/closure.

A recovery record retains the attempted verification report, its method/run/target/manifest identity and original outcomes, inside a failed operation. Timing must enclose the original attempt. A nested guest pass does not become an overall pass when reporting fails. A separate failed-operation index hashes the exact failure bytes and must match its operation, method, run and terminal outcome.

First pass: structural schemas and valid preflight/build/recovery records. Second pass: false success/completion, missing errors, impossible stage order, preflight execution claims, changed failure bytes, reversed time, unsafe evidence, recovery identity/target/time mismatch and missing manifest binding. All 13 test methods pass. Alongside the other suites, 53 M2 synthetic contract tests pass; existing M1 design and dashboard suites also pass.

These records describe claims; runtime must still authenticate source artifacts, actual cleanup and log bytes. Neither a schema nor a self-consistent recovery object proves that the retained nested record came from execution. Stable file handles, owned-resource checks, trusted recipes, byte captures and atomic publication remain implementation requirements.

Remaining P6 work: successful M2 build-result/index binding and complete dispatch examples; final real asset/source distribution package and hardware inventory. Failure to publish even a recovery record must remain a nonzero CLI outcome with an explicit error; no index can be promised when its destination itself is unwritable. No synthetic record is placed in the runtime execution directory.

Reproduce with design dependencies available:

```text
python tools/m2_failure_contracts.py
python tools/test_m2_failure_contracts.py -v
```
