# Console driver

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Provide serial output and interactive input. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **CONSOLE-001:** Provide serial output and interactive input through an explicitly documented interface.
- **CONSOLE-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **CONSOLE-003:** Supply a repeatable procedure demonstrating: boot text and interactive input work using documented wiring and settings.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: BSP, HAL.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: initialize serial device; transmit bytes; receive input; report device errors. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Initialize serial device"]
  S1["transmit bytes"]
  S0 --> S1
  S2["receive input"]
  S1 --> S2
  S3["report device errors"]
  S2 --> S3
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- Boot text and interactive input work using documented wiring and settings.
- Exercise invalid input and unavailable-resource behavior defined by CONSOLE-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

UART selection, buffering, polling versus interrupts, line endings. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine CONSOLE-001 through CONSOLE-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
