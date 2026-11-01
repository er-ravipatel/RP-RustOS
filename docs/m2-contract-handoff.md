# M2 contract handoff and remaining P6 work

Current update: the [DTB reproduction](m2-dtb-reproduction.md) has now passed twice with exact bytes. Earlier prerequisite/reproduction gaps below describe the preceding checkpoint; final source/notice binding in the production asset lock remains open.

2026-11-01. Current checkpoint after decisions D15–D18. M1 remains accepted; M2/P6 remain in progress. This document supersedes earlier contract-check notes' lists of unfinished schema definitions, without changing their recorded test counts or execution limits.

## Checked design artifacts

| Boundary | Contract and checks |
| --- | --- |
| Pi profile and firmware lock | [Input contracts](m2-input-contract-verification.md); 12 synthetic tests |
| Manifest, image inspection and hardware report | [Output contracts](m2-output-contract-verification.md); 17 synthetic tests |
| Hardware session, proposed CLI syntax and verification index | [Session contracts](m2-session-contract-verification.md); 11 synthetic tests |
| Preflight/build failures, reporting recovery and failed-operation index | [Failure contracts](m2-failure-contract-verification.md); 13 synthetic tests |
| Successful build index and strict index dispatch | [Dispatch utility](../tools/m2_index_dispatch.py) and [tests](../tools/test_m2_index_dispatch.py); 5 synthetic tests |

Successful-build indexes now bind exact manifest bytes, the CLI build result and manifest path. They explicitly record verification not run. A build index cannot contain a hardware method, a verification pass or error diagnostics alongside success. The dispatcher separately handles completed build, completed verification and failed operations, rejecting unknown versions/kinds and missing required byte inputs.

Two passes for this final slice: structural positive build/verify/failure dispatch first; changed manifest bytes, differing result paths, unknown fields, error diagnostics, verification promotion and missing inputs second. All 58 unique M2 test methods pass in one discovery run. Existing 12 M1 design tests and 25 dashboard tests also pass. This is Codex self-review, not independent runtime or hardware verification.

## Implementation gates that remain open

1. Finish the real firmware/source package and its licence inventory. The [licensing research](m2-asset-licensing.md) identifies the Linux source hint but does not provide a complete corresponding-source package or reproduced DTB. Freeze the final asset lock only after this work.
2. Review exact Cortex-A53 transition/register masks, GPIO/mailbox transport and memory-ordering implementation against primary specifications before executing Pi startup code. High-level boot/console direction is agreed; the instruction sequence is not implemented.
3. Implement target selection, stable input consumption, packaging, serial capture and index/importer support in the ordered P7–P9 queue. These Python contracts do not enable any of those runtime paths. Add runtime negative/ownership/atomic-publication checks; do not substitute schema fixtures for them.
4. Record card/reader, power, GPIO header and 3.3 V adapter/Windows COM port before physical preparation. No board setup has been confirmed. This does not prevent source-package investigation or other host-only work.

The runtime must also bind all boot-content origins to the exact lock/source inputs, validate actual image/log bytes and filesystem identities, and enforce trusted recipe parameters. The design validators check declared relationships, not authentic execution. CLI syntax fixtures are a proposal parser, not supported Rust command options. Historical schema-1 records continue through their existing strict runtime reader.

## Reproduction

With the optional design dependencies installed, from the repository root:

```text
python -m unittest discover -s tools -p "test_m2_*.py" -v
python tools/test_design_contracts.py
python -m unittest discover -s docs/dashboard -p "test_*.py" -v
```

No synthetic records are written under the runtime execution index directory. Contract evidence appears as P6 documentation in the dashboard, not a successful build or hardware run.
