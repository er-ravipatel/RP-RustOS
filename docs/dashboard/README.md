# Live progress dashboard

From the repository root run:

```text
python docs/dashboard/server.py
```

Open http://127.0.0.1:8765/docs/dashboard/ in a browser. Python 3 is required; there are no third-party dependencies. Stop with Ctrl+C. The read-only server binds to localhost and serves repository files, including documentation links. Do not expose it through a public tunnel.

Run only one copy. If startup says port 8765 is already in use, open the URL above: the dashboard may already be running. To restart a terminal-launched copy, press Ctrl+C in that server's terminal before running the command again. A port conflict does not stop the existing server.

The page reloads [the progress register](../progress.json) every five seconds without caching. Edit that JSON file and save to update the displayed status. The page is read-only: it does not write changes or store private status in browser storage. There is no hosted service or external tracker.

Each feature has seven stages: requirements, analysis, design, review, documentation, implementation, verification. Each stage has `status` and `evidence` fields. Use `draft`, `not_started`, `in_progress`, `blocked`, or `complete`. Evidence is an array of repository-relative references or explanatory review/test records. Completed stages require nonempty evidence. Use the feature's `blockers`, `next_action`, and `updated_at` fields to explain its current state. Maintain the top-level `updated_at` too.

Run `python docs/dashboard/check.py` to validate the register. A completed stage is a recorded assertion requiring human review; the dashboard does not prove its evidence. Documentation proposals are recorded as drafts. Review, implementation, and verification start not started. Percentages count completed stage cells equally and do not estimate remaining effort.

The dashboard shows last successful refresh separately from the register timestamp. If refresh or validation fails, it marks the view stale and retains the last valid data. No workflow status is inferred from time passing, file creation, builds, or conversations.

## Planning and execution visibility

The additional [planning register](../tracking.json) contains agreed decisions, all six gap discussions, milestones, 15 assembler requirement proposals with seven stages each, component responsibilities, acceptance criteria, design/change/test references, workflow policies, research-tool readiness, and recorded run results. Both registers refresh every five seconds. Requirement search and milestone filters affect only the view; filter preferences are stored in browser session storage, never engineering status.

Run `python docs/dashboard/check_tracking.py` to validate planning states, evidence paths, requirement metadata, and run consistency. Recorded execution evidence now includes a `kernel-development` run from P4. It is distinct from an assembler-produced bundle or production verification report. Records are maintained explicitly until report ingestion is implemented.

Each recorded run requires `id`, `target`, `artifact`, `updated_at`, `status`, `verification_scope` (`emulator`, `hardware`, or `none`), `cleanup`, `evidence` (repository-relative file paths), and `steps` (each with `name`, `status`, `evidence`). Runtime states are `not_run`, `running`, `passed`, `failed`, `cancelled`, `timed_out`, and `skipped`. A passed run needs evidence and must not contain failed, cancelled, timed-out, or running steps. Record artifact identity/hash in its manifest and reference the manifest in the evidence. Cleanup remains a descriptive record pending concrete runner design.

Policy agreement does not mean implementation completion. The original OS component stages have been reconciled to draft rather than active. Tool readiness also stays separate from OS delivery. The recorded plan reevaluation identifies remaining technical decisions.

## Active-work queue

The planning register includes `work_policy` and ordered `work_items`. The dashboard shows selected milestone, current slot usage, exit conditions and next actions. In-progress and blocked tasks occupy slots. The agreed limit is two active items: at most one primary and one research item, both within the selected milestone. Validators reject excess slots and multiple active milestones. Queue items stay not started until work actually begins. Draft requirement stages are not counted as independent active tasks.

P4 kernel development evidence is labeled by `kind` so real emulator checks are visible without implying assembler delivery. The original subsystem outlines remain separate from the completed M1 emulator startup slice.

## Automatic execution records

`build` and `verify` atomically publish terminal outcome indexes under repository `.rustos/executions/`. The server merges explicit indexed outcomes into its tracking response every five-second refresh; the planning file remains separate and read-only. This does not stream in-flight command progress. Failed preflight records also appear. Imported reports are checked against retained manifest/log identities, exact captured markers and cleanup outcomes. Invalid entries show import errors. Valid report links use registered localhost `/execution/<id>/report` routes, including explicitly indexed external reports.

Profile 0.1.1 includes the approved instruction-counting setting. New runs show `assembler-verify`; historical trial runs keep `assembler-verify-provisional`. Neither label alone closes M1. See [verifier evidence](../p5-verification.md). Run `python -m unittest discover -s docs/dashboard -p "test_*.py" -v` for importer and localhost HTTP checks. Visual browser verification is still outstanding.

The [M1 acceptance record](../m1-acceptance.md) closes the scoped emulator milestone. Fault-injected cleanup observations are labelled `assembler-verify-fault-fixture`; incomplete reporting failures retain their own evidence links. Build diagnostics distinguish compilation/packaging passes, skipped packaging and verification not run. The broader subsystem rows and M2 hardware-image requirements remain separate from completed M1 feature rows.

Windows uses an exclusive localhost listener. A second server on the same port must fail rather than returning requests from different importer versions. When refreshing a server, inspect all listeners and stop only processes confirmed to run this project's dashboard.

## Code work summaries

The dashboard begins with a visible code-work summary table from `work_updates` in the planning register. Every code change must record what changed, validation results, remaining work or limitations, and evidence links. Commit hashes link to GitHub; entries committed with their own record link to project history until an immutable hash is recorded. Summaries are explicit records, not automatic verification or live build telemetry. Both registers refresh every five seconds. This requirement is also recorded in the root project instructions.
