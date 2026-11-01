# Catalog discovery and process ownership — proposal for confirmation

Approved by the user on 2026-10-31 after two-pass review. This establishes the design baseline; production process ownership and resolver behavior remain unimplemented.

## Repository-local discovery

Use an explicit common `--repo <directory>` option for the initial four CLI operations. Resolve it once to a canonical local repository root. Use only `<repo>/profiles/<target-id>.toml` and `<repo>/catalog/modules.toml`, with identifier validation before constructing a target path. `--config` resolves from the invocation directory; configuration `output_dir` remains relative to the configuration file. Relative source paths resolve from the repository root, not from the configuration directory.

Do not search ancestor directories, the network, or globally installed catalogs implicitly. Reject profile filename/ID mismatches, duplicate module/feature IDs, unknown fields and paths that escape the root. Resolve and check actual filesystem identities at use, not only path strings. Repository-local source declarations do not by themselves prove build readiness. Current examples remain design fixtures; production profile/catalog directories are created with the actual assembler implementation.

For verify, the supplied manifest must bind to an installed repository target/recipe definition with matching identity. Module catalogs and manifests cannot inject arbitrary executable commands. Tools are resolved through a distinct local tool configuration or checked executable discovery. The precise tool-configuration storage format is implementation work; no absolute developer-specific path is committed as a portable target setting.

## Windows process ownership

Use one owned Windows Job Object per active external-tool invocation tree. Set kill-on-job-close and prohibit breakaway. Create the initial child suspended, assign it to the job before resuming, and retain process/job handles. If ownership establishment fails under host/nested-job constraints, fail the step before resuming work; do not fall back to terminating processes by executable name.

The coordinator owns cancellation, deadlines, handles and cleanup. Build/verifier modules own typed argument construction and interpretation of tool output. Child process IDs alone are insufficient authority because IDs may be reused; use retained handles and the owned job. This is lifecycle containment, not a sandbox for untrusted code.

For QEMU, use a unique local Windows duplex named pipe for the QMP control channel, with guest serial kept separate. Perform the QMP handshake before commands. After the expected marker, send `quit` through that owned channel; wait up to five seconds. If QEMU/control setup fails, or settlement is not complete by the stop budget, terminate the owned job and wait a further five seconds. Record whether normal stop or forced termination was used. Any unresolved process/pipe/reader settlement prevents success.

Use a unique unpredictable pipe name and verify/connect only the endpoint belonging to the created process; pipe-name secrecy alone does not establish ownership. Native pipe access/identity details and QMP initialization must be proven in implementation. No network listener is needed for this proposal. Named-pipe access failure is a prerequisite/runtime failure, not a reason to expose a public TCP control port.

Use dedicated output readers and a monotonic clock; the ten-second scenario deadline begins at successful process creation, including runner setup. Reject oversized protocol lines and bounded-output overflow with diagnostics instead of unbounded buffering. Proposed limits: 4 KiB per protocol line and 1 MiB per captured guest stdout/stderr stream per scenario; limits must be recorded by the recipe/version and verified in tests. Retain bounded logs and an explicit truncation/overflow error. A captured success marker cannot override overflow, wrong-scenario markers or an earlier fault.

## Review pass 1 — source behavior

- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) supports grouped lifecycle management; child association and breakaway/nested-job behavior require explicit handling.
- [Windows process creation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw) supports explicit executable selection and creation flags. Suspended creation prevents the child from running before assignment.
- [QEMU invocation](https://www.qemu.org/docs/master/system/invocation.html) documents the Windows duplex pipe character backend. This establishes an available transport design, not a completed QMP handshake/permission test on this host.

## Review pass 2 — failure and contract consistency

Walked these cases against the approved rules: assignment fails before resume; nested jobs prevent ownership; process spawns children; cancellation arrives during launch; QMP fails to connect; guest floods output; final marker arrives near deadline; child exits unexpectedly; pipe remains open in a descendant; artifact changes; destination becomes occupied; cleanup does not settle. In each case, success requires explicit ownership, expected evidence and bounded settlement; unsupported states fail rather than silently weakening the contract.

Implementation tests must exercise these behaviors on the actual host. Existing environment probes stop a directly owned QEMU process and do not establish production Job Object/QMP integration. This design does not claim that tests for process trees, named-pipe ownership, overflow or nested-job admission have run.

## Confirmed choices

1. Explicit `--repo` and fixed repository-local profile/catalog locations.
2. Windows Job Object ownership established before child execution; owned QMP stop followed by job termination if necessary.
3. Recipe-recorded output limits and explicit failure on overflow.

P2 design is complete with these approved choices, strict schemas, examples and design fixtures. Parser/resolver implementation is P3; kernel startup is P4; runner and automatic dashboard ingestion are later integration work.
