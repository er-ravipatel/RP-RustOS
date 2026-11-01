# Interactive shell

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Parse commands and launch supported programs. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **SHELL-001:** Parse commands and launch supported programs through an explicitly documented interface.
- **SHELL-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **SHELL-003:** Supply a repeatable procedure demonstrating: valid commands execute; malformed input and failed launches preserve the prompt.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: Console input, init, syscall ABI, program loading.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: read line; parse command; resolve program; launch; wait; display result. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Read line"]
  S1["parse command"]
  S0 --> S1
  S2["resolve program"]
  S1 --> S2
  S3["launch"]
  S2 --> S3
  S4["wait"]
  S3 --> S4
  S5["display result"]
  S4 --> S5
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- Valid commands execute; malformed input and failed launches preserve the prompt.
- Exercise invalid input and unavailable-resource behavior defined by SHELL-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

Grammar, built-ins, path lookup, signals and job-control scope. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine SHELL-001 through SHELL-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
