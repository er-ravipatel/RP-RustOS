# C runtime startup

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Start and terminate C user programs correctly. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **CRT-001:** Start and terminate C user programs correctly through an explicitly documented interface.
- **CRT-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **CRT-003:** Supply a repeatable procedure demonstrating: a minimal C program receives documented startup state and returns an exit code.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: Loader, syscall ABI, memory, C toolchain selection.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: load image; initialize runtime state; call main; report exit; release process. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Load image"]
  S1["initialize runtime state"]
  S0 --> S1
  S2["call main"]
  S1 --> S2
  S3["report exit"]
  S2 --> S3
  S4["release process"]
  S3 --> S4
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- A minimal C program receives documented startup state and returns an exit code.
- Exercise invalid input and unavailable-resource behavior defined by CRT-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

C ABI, target triple, argument layout, global initialization. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine CRT-001 through CRT-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
