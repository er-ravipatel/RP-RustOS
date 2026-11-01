# P5 Windows execution foundation

Status: initial P5 foundation, checked on 2026-11-01. At this increment the CLI implemented only `validate` and `plan`. The subsequent [snapshot build increment](p5-build-verification.md) connects these primitives to `build`. P5 and M1 remain in progress pending production verification and report integration.

## Implemented boundary

The Windows host library now creates each process suspended, assigns it to a private kill-on-close Job Object, and only then resumes its initial thread. It restricts inherited handles to stdin and the two captured log handles. A root process exiting does not imply its descendants have settled. Job accounting, rather than a search by executable name, determines when the owned tree is empty.

The noninteractive tool supervisor polls cancellation, output size, process-tree completion and its deadline. Cancellation, timeout and overflow terminate the owned job and allow five seconds for settlement. Retained stdout/stderr captures are capped after settlement. Files may briefly exceed the capture cap between polls: this is a retention limit, not a filesystem quota. Errors and unsuccessful settlement must prevent a future caller from reporting success.

Additional primitives provide stable read handles denying writes/deletion while held, same-volume publication without replacement, and named-pipe server PID/available-byte queries. The pipe helpers have not yet been integrated with or tested against QEMU's QMP channel.

Implementation: [Windows execution primitives](../tools/assembler/src/native.rs), [process integration tests](../tools/assembler/tests/windows_process.rs), and [test fixture](../tools/assembler/tests/support/job_fixture.rs). The fixture binary requires the explicit `test-fixtures` Cargo feature and is not part of the normal application build.

## Two checks

The first runtime pass exposed an incorrect test assumption: Windows also creates a `conhost.exe` within the owned job. Inspection of the test job's own process IDs established that both fixture processes and the console helper were contained. Tests now assert ownership of the expected root/descendant IDs and require zero remaining job processes after cleanup, without assuming an exact initial count.

A subsequent sequential pass passed 28 Rust test methods: 17 existing inspection tests, one quoting unit test, and ten Windows integration tests. These cover tree termination, descendants surviving root exit, drop cleanup, isolation from an unrelated owned job, timeout, cancellation, overflow failure and retained log limits, exact argument delivery including Unicode/quotes/trailing slashes, publication collision preservation and stable input locks.

Independent static checking uses Clippy with warnings denied, excluding two pre-existing P3 lints (`result_large_err` and `uninlined_format_args`). The intentional orphan fixture has a local documented lint allowance because root exit before child exit is the behavior under test. These exclusions are not a claim of an entirely warning-free unqualified Clippy run.

Reproduce from the repository root:

```powershell
cargo test --manifest-path tools/assembler/Cargo.toml --locked --features test-fixtures
cargo test --manifest-path tools/assembler/Cargo.toml --locked --features test-fixtures -- --test-threads=1
cargo clippy --manifest-path tools/assembler/Cargo.toml --locked --all-targets --features test-fixtures -- -D warnings -A clippy::result_large_err -A clippy::uninlined_format_args
```

## Remaining P5 acceptance work

- Connect CLI `build` and `verify` to the execution backend with explicit prerequisite checks.
- Build both kernel variants from one identified source snapshot and publish a validated immutable manifest/bundle.
- Bind QMP's unique named pipe to the owned QEMU PID; enforce the approved marker, stop, kill and output rules across both scenarios.
- Produce strict final reports for success and failure, and ingest those execution records into the dashboard automatically.
- Run complete configuration-to-bundle-to-verification acceptance and rejection cases before declaring M1 delivered.

The dashboard records this foundation as partial implementation evidence. None of these primitive tests is labelled an OS build or a production emulator verification run.
