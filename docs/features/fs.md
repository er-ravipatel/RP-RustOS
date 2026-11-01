# Filesystem

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Offer consistent file access and eventual persistence. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **FS-001:** Offer consistent file access and eventual persistence through an explicitly documented interface.
- **FS-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **FS-003:** Supply a repeatable procedure demonstrating: read and write behavior is repeatable; persistent files survive reboot when enabled.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: Memory; block driver for persistent backend.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: resolve path; check access; operate on file; return result; release handle. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Resolve path"]
  S1["check access"]
  S0 --> S1
  S2["operate on file"]
  S1 --> S2
  S3["return result"]
  S2 --> S3
  S4["release handle"]
  S3 --> S4
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- Read and write behavior is repeatable; persistent files survive reboot when enabled.
- Exercise invalid input and unavailable-resource behavior defined by FS-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

Path rules, handle ownership, filesystem format, recovery policy. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine FS-001 through FS-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
