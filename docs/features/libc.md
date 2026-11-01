# C library subset

**Status:** initial proposal; requirements, analysis, design, and documentation drafted, not active or approved. Review, implementation, and verification have not started.

## Goal and scope

Implement the C interfaces required by selected programs. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **LIBC-001:** Implement the C interfaces required by selected programs through an explicitly documented interface.
- **LIBC-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **LIBC-003:** Supply a repeatable procedure demonstrating: selected APIs pass defined success and failure cases; unsupported APIs are listed.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: C startup, syscall ABI, allocator, filesystem.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: application calls supported api; translate to kernel request; return result or error. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
flowchart TD
  S0["Application calls supported API"]
  S1["translate to kernel request"]
  S0 --> S1
  S2["return result or error"]
  S1 --> S2
  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- Selected APIs pass defined success and failure cases; unsupported APIs are listed.
- Exercise invalid input and unavailable-resource behavior defined by LIBC-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

Supported functions, errno model, allocation and I/O semantics. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine LIBC-001 through LIBC-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
