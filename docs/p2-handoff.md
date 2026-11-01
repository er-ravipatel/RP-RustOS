# P2 design completion and P3 handoff

P2 design completed on 2026-10-31 after the user's confirmation of the remaining twice-reviewed catalog/process/output choices. Completion applies to design deliverables, not an implemented assembler or operating system.

## Baseline

- [TOML input contracts](configuration-design.md), [examples](examples/m1.toml), [target profile](examples/qemu-virt-a53.toml), [module catalog](examples/modules.toml), and [fixture expectations](examples/fixture-expectations.json).
- [Four CLI operations](cli-design.md) and [report/manifest baseline](report-contract.md).
- [Kernel startup baseline](kernel-startup-contract.md) and [confirmed verification/publication policy](verification-publication-review.md).
- [Repository discovery and process ownership](catalog-and-process-design.md), including bounded output and failure on unresolved cleanup.
- [Strict design schemas and tests](schemas/README.md).

Detailed CLI numeric exit-code values remain proposed in the CLI document; they do not block parser/resolver implementation, and must be reconciled before its public CLI acceptance gate. Windows Job Object/QMP design is approved but not empirically established by the temporary process probes. No new kernel timing or stability guarantee is implied.

## Checks

Two passes covered structural schema constraints and independent cross-record false-success cases. Twelve design-contract test methods and eight tracking test methods passed. These include synthetic fixtures and do not establish real artifact hashes, OS behavior, process containment, or source availability. TOML syntax was checked, including rejection of the deliberately malformed fixture. Graph resolution fixtures are specified but not yet executed by a resolver.

## P3 implementation scope

Implement strict TOML loading; explicit repository/profile/catalog discovery; field and compatibility validation; dependency closure, cycles and conflicts; deterministic dependency-first ordering with all selection reasons; readiness diagnostics; and validate/plan behavior without compilation or OS output directories. Use the approved schemas as contracts rather than inventing incompatible result shapes.

P3 acceptance must execute all structural and graph fixtures, reject missing/duplicate/unsupported metadata, verify stable ordering and explanations, preserve input identities, and demonstrate no build subprocess or output creation during inspection. Missing planned sources produce readiness false, while unknown module IDs remain errors. Root workspace placeholders must not prevent host-tool verification; select a deliberate host crate layout when implementation begins.

P4 owns the minimal Rust kernel, startup and panic variants. P5 owns build/packaging integration, artifact publication, the production verification runner, report ingestion and end-to-end evidence. Tests for process trees, output overflow, QMP failures, artifact changes, and publication races remain required there.

## Current delivery state

P1 environment selection/probes complete. P2 design complete. P3 queued. No assembler build runs, verified OS requirements, bootable Raspberry Pi image, or actual RustOS startup/panic results exist yet. One selected milestone and the agreed two-item limit continue to apply.
