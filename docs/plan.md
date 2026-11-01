# Documentation and delivery plan

## Goal

Produce a reviewable specification for the RustOS assembler and its OS modules before implementing risky interfaces, then track delivery against explicit acceptance criteria. The assembler selects compatible components and produces a bootable artifact or image for its target. Initial scope is RustOS-only, with emulator verification followed by Zero 2 W hardware verification and later Pi 5 support. See the [agreed product direction](product-direction.md) for revised M1/M2 scope and outstanding discussion items.

The phase table below is a documentation work breakdown. The milestone definitions in the agreed product direction govern delivery scope; the older feature outlines still need reconciliation as the gap discussions proceed.

## Deliverables

1. Requirements: user or developer outcome, scope, failure behavior, and measurable acceptance criteria for each feature.
2. Analysis: prerequisites, hardware assumptions, alternatives, risks, and unresolved questions.
3. Design: ownership, interfaces, state transitions, errors, and security boundaries.
4. Architecture: system context, subsystem dependencies, deployment boundaries, and diagrams.
5. Workflows: normal operation, startup/shutdown where applicable, and failure recovery.
6. Review: a named reviewer, date, findings, dispositions, and explicit approval or requested changes.
7. Implementation: changes linked to requirements, with repeatable verification evidence.
8. Progress: per-stage status, blockers, timestamps, evidence, and next actions in the dashboard.

## Sequence

| Phase | Documentation focus | Exit gate |
| --- | --- | --- |
| A. Scope baseline | Board, purpose, first release, exclusions, initial feature requirements | Requirements reviewed; assumptions and open questions recorded |
| B. First build and boot | Build tools, kernel entry, HAL, BSP, console, image layout | Interfaces and boot contract reviewed; reproducible build and hardware procedures defined |
| C. Kernel foundations | Memory, exceptions, timer, scheduler, synchronization | Ownership and fault behavior reviewed; subsystem verification specified |
| D. User environment | Syscalls, isolation, IPC, init, shell, utilities | ABI and process lifecycle reviewed; negative tests defined |
| E. Storage | Block access, filesystem, persistence | Error recovery and reboot consistency requirements reviewed |
| F. Runtimes and portability | C startup, libc subset, MicroPython, packaging, second-board exploration | Supported compatibility surface and portability criteria documented |

These phases express dependencies, not dates. Storage analysis can proceed alongside userland; runtime implementation depends on a stable enough ABI and memory model.

## Feature document standard

Every specification must include purpose, requirements with stable IDs, dependencies, proposed design, a workflow diagram, failure paths, acceptance criteria, open decisions, and a review record. Add sequence diagrams where interactions cross subsystems and state diagrams where lifecycle is central. Use Mermaid in Markdown so diagrams can be reviewed with source.

Initial feature documents are proposals. Before marking requirements complete, replace broad goals with observable behavior and enumerate errors. Before marking design complete, define concrete signatures, ownership, synchronization, and resource limits. Before marking implementation complete, link actual changes. Before marking verification complete, record commands, environment, expected and actual results.

## Review and change control

Record architectural decisions in `docs/decisions/` when decisions are made; identify the problem, alternatives, chosen approach, consequences, and superseded decisions. No ADR is approved merely by creating its file.

For each review, record reviewer, date, specification revision, findings, resolution, and outcome in the feature document. Reopen affected stages when requirements or interfaces change. Keep requirement IDs stable, and record retired requirements instead of silently reusing their IDs.

## Reporting rules

The dashboard reports stage counts and feature rows from [progress.json](progress.json). Allowed states are `draft`, `not_started`, `in_progress`, `blocked`, and `complete`. Draft identifies an available proposal rather than active work. Each completed stage needs evidence. The overview percentage is the unweighted fraction of completed stage cells, not effort, elapsed time, release readiness, or implementation percentage. Implementation and verification receive separate counters.

Update the register after a meaningful change in the same change set as the work. Record a next action and blockers. Review pending items at the start of each work session and reconcile evidence at the end. There is no autonomous observation of discussions, approvals, external CI, or hardware attached elsewhere.

## Agreed scheduling and reevaluation

Follow the [ordered M1 queue and two-item limit](priorities.md). One milestone is selected for delivery; only one primary item and one optional supporting research item may be active, counting blocked tasks until explicitly returned to the backlog. Component outlines and acceptance proposals are drafts, not active tasks. The [reevaluation](plan-evaluation.md) identifies remaining environment, schema, interface and verification decisions.
