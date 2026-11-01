# Delivery priorities and active-work policy

Agreed on 2026-10-31: one active delivery milestone and at most two active work items: one primary design/implementation item and one supporting research item. These are task limits, not limits on the number of dependencies that a task can touch. They do not authorize parallel agents.

## Ordered M1 work queue

Current outcome, 2026-11-01: all five M1 queue items are complete within the [emulator acceptance scope](m1-acceptance.md). No primary implementation item is active. M2 hardware-image work remains not started until selected; the historical initial reconciliation below does not override the current register.

| Order | Work item | Exit condition |
| --- | --- | --- |
| 1 | Select emulator, machine and development environment | Recorded compatible target, tools, invocation, and verification approach |
| 2 | Define configuration, target profile and module metadata | Concrete schemas, example minimal configuration, and invalid-input fixtures |
| 3 | Implement validation and dependency resolution | Required modules and reasons are inspectable; invalid combinations fail before compilation |
| 4 | Build minimal kernel with serial startup and panic diagnostics | Artifacts build from documented inputs and execute in the selected emulator |
| 5 | Connect assembly, manifests and automated verification | Configuration-to-artifact workflow produces manifest and bounded startup/panic checks with evidence |

Pi hardware research can support M1. Physical Zero 2 W image verification is M2; Pi 5, shell, storage services, scheduling and runtimes remain later delivery work. The queue does not remove those features from scope.

## Status and scheduling rules

- `draft`: an outline or proposal exists, but the stage is not currently being worked on or approved.
- `not_started`: work has not begun and no substantive draft exists for that stage.
- `in_progress`: the stage is actively being worked on as part of an active work item.
- `blocked`: work cannot proceed; record the dependency and next action. A blocked work item still occupies its slot until explicitly returned to the backlog.
- `complete`: exit conditions are met and evidence is linked. Agreement on policy does not complete implementation.

The work queue, not every requirement stage, is the unit of the two-item limit. Multiple requirements may belong to one work item. Record those associations as their interfaces are refined. Do not create separate active work for each draft document.

Select the next primary item only after completing or explicitly returning the current primary item to the backlog. The optional research slot can be empty. Backlog items do not start merely because they are visible on the dashboard. No dates or effort estimates have been agreed.

## Initial reconciliation

All initial OS feature outlines and assembler requirement proposals are drafts. Review, implementation and OS verification remain not started. M1 is the selected delivery milestone; its implementation completion remains not started. Environment/target selection is the next primary work item and is queued until actual research begins. No supporting research task is active yet.

The dashboard exposes queue order, activity, slot usage, milestone, and source evidence. Validators reject over-limit active queues. See the [reevaluation](plan-evaluation.md) for remaining implementation-readiness decisions.
