# Interprocess communication

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Exchange data between isolated tasks. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **IPC-001:** Exchange data between isolated tasks through an explicitly documented interface.
- **IPC-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **IPC-003:** Supply a repeatable procedure demonstrating: blocking, peer termination, and queue exhaustion have defined outcomes.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: Scheduler, memory, syscall ABI.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: create endpoint; send or wait; transfer data; wake receiver; close endpoint. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Create endpoint"]
  S1["send or wait"]
  S0 --> S1
  S2["transfer data"]
  S1 --> S2
  S3["wake receiver"]
  S2 --> S3
  S4["close endpoint"]
  S3 --> S4
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- Blocking, peer termination, and queue exhaustion have defined outcomes.
- Exercise invalid input and unavailable-resource behavior defined by IPC-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

Message ownership, buffer limits, endpoint permissions. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine IPC-001 through IPC-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
