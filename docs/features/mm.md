# Memory management

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Allocate memory and isolate address spaces. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **MM-001:** Allocate memory and isolate address spaces through an explicitly documented interface.
- **MM-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **MM-003:** Supply a repeatable procedure demonstrating: allocation exhaustion and invalid mappings fail without corrupting owned memory.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: Board memory map, kernel exception handling.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: discover usable memory; allocate pages; create mappings; reclaim ownership. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Discover usable memory"]
  S1["allocate pages"]
  S0 --> S1
  S2["create mappings"]
  S1 --> S2
  S3["reclaim ownership"]
  S2 --> S3
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- Allocation exhaustion and invalid mappings fail without corrupting owned memory.
- Exercise invalid input and unavailable-resource behavior defined by MM-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

Physical allocator, address layout, page tables, heap policy. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine MM-001 through MM-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
