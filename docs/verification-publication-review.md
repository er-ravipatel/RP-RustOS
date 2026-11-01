# Two-pass review of M1 verification and publication

Date: 2026-10-31. Status: revised verification and publication policy confirmed by the user on 2026-10-31. This approval establishes the policy; it does not implement or verify the kernel tests or publisher.

## Pass 1 — source and feasibility check

Reviewed QEMU invocation documentation, Microsoft MoveFileExW documentation, the installed emulator probe, and the current profile/configuration/CLI/workflow contracts.

- QEMU's selected machine/CPU/serial invocation has already run a synthetic ELF successfully. This does not verify a RustOS panic handler or actual startup invariant.
- The normal and panic scenarios must use separate artifacts and exact manifest hashes. Verify must not rebuild or substitute a different variant.
- A panic marker is meaningful only when emitted from the deliberately selected panic handler path. Printing the same marker from ordinary startup would not establish panic diagnostics.
- Ten seconds is a proposed configurable recipe deadline, not a measured RustOS timing guarantee. The synthetic fixture used five seconds and cannot establish the RustOS production deadline.
- A directory move must remain on the same volume. A no-replacement operation must reject a destination that appears after the initial check. Staging next to the destination supports this requirement; a check-then-copy approach does not.
- Do not claim power-loss durability, protection against all concurrent mutation, or guaranteed cleanup/reporting after abrupt host termination.

Sources: [QEMU invocation](https://www.qemu.org/docs/master/system/invocation.html), [Windows MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw).

## Pass 2 — independent consistency and failure check

Compared the recommendations against ASM-005 through ASM-009 and ASM-012 through ASM-015, CLI build/verify separation, readiness semantics, output preservation, and dashboard reporting.

An isolated temporary-directory experiment used Windows MoveFileExW with flags 0. Moving staging to an absent sibling destination succeeded. A second move to that occupied destination failed with Windows error 183; the original artifact bytes and rejected staging bytes remained unchanged. This validates those tested publication behaviors only, not a complete production publisher, crash recovery, adversarial path-race protection, or other filesystems.

Tracking validation and eight regression tests passed. These tests validate recorded state, evidence and work limits; they do not test the future kernel/verification runner.

### Scenario review and required behavior

| Scenario | Required outcome |
| --- | --- |
| Normal kernel emits its final boot marker | Stop owned emulator, drain output, check result and process settlement before passing |
| Deliberate panic variant reaches the panic handler and emits its final expected marker | Same controlled stop/drain/settlement; record the variant and handler diagnostics |
| Expected marker missing at deadline | Timed out; never a success inferred from guest silence |
| Marker arrives in partial chunks | Buffer complete lines; match an exact protocol line, not arbitrary substrings |
| Unexpected panic/exception marker or wrong scenario marker observed | Fail, even if expected marker was also captured |
| Emulator exits before runner-requested stop | Fail for this halt-loop recipe; do not infer success from exit code alone |
| Cleanup does not settle owned processes | Cleanup failure overrides success; retain prior scenario observations |
| Artifact differs from manifest | Fail before guest launch |
| Build/package fails | Keep incomplete staging and logs; do not publish a complete bundle |
| Final destination exists initially or appears before publication | Reject without replacing it; preserve staging diagnostics |
| Report publication or storage fails | Explicit failure/unresolved report state; do not present stale output as this run's success |
| Requested verification fails after a successful build | Preserve immutable bundle and separate failed verification report |

These are reviewed expected behaviors, not executed kernel/runtime tests. Automated fixtures must prove them during implementation.

## Confirmed policy

1. Build two artifacts from the same identified source inputs: normal `kernel.elf` and a controlled `kernel-panic-test.elf` variant. Record distinct variant identity and hashes in the manifest. The panic selection is an internal build variant, not an arbitrary user shell command.
2. Normal startup emits the exact complete line `RUSTOS_BOOT_OK` only after defined M1 initialization, then idles. The deliberate panic handler emits diagnostics followed by the exact final line `RUSTOS_EXPECTED_PANIC`, then halts. Ordinary unexpected panics and exceptions use distinct failure markers. Concrete initialization invariants and panic-trigger placement remain kernel startup design work.
3. Each scenario has a ten-second wall-clock marker deadline from successful process creation. Record the configured limit; adjust only through an explicit, versioned recipe change supported by observations. Cleanup has a separate bounded budget, initially five seconds for stop and another five seconds for forced termination/settlement. A failed settlement never passes.
4. On a final expected marker, request owned-emulator shutdown immediately, drain remaining output, reject captured contradictory markers, and confirm settlement. This is a finite boot/panic smoke test, not proof of long-term idle stability. Marker matching alone does not prove all kernel invariants.
5. Use a unique sibling staging directory. After artifacts/manifests are closed, validated and hashed, publish through a same-volume no-replacement directory move. Recheck path identity and output/source separation at the consuming operations. If publication fails, retain staging as incomplete; never implicitly replace another output. Crash durability and adversarial path-race guarantees require separate implementation evidence.
6. Verification reports live outside the immutable bundle, have unique run IDs and explicit completeness/outcome, and reference the manifest/artifact hashes. Dashboard reports build, packaging, each scenario and cleanup separately. Automatic ingestion remains to be implemented.

## Remaining limitations before implementation readiness

Full RustOS tests are unimplemented. Streaming output limits, concrete cancellation/process ownership mechanisms, exact manifest/report schemas, startup register/stack/BSS contracts and supported filesystem/path guarantees still need implementation design. This review tightens the proposal; it does not mark P2, requirements, or tests complete.
