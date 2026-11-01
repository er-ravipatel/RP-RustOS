# RustOS engineering documentation

**Status: proposed design.** No operating-system features have been implemented or verified. Documentation describes intent until evidence establishes otherwise.

Start with the [documentation plan](plan.md), [architecture](architecture.md), [feature specifications](features/README.md), and [progress register](progress.json). Use the [dashboard instructions](dashboard/README.md) to view live recorded progress.

The [research reference index](research-index.md) keeps the Redox OS, Ventoy and Phil Opp blog_os analyses, pinned source evidence and reuse recommendations together for future development.

The [agreed product direction](product-direction.md) records the OS assembler goal, RustOS-only initial scope, emulator-first verification, Zero 2 W and Pi 5 target order, and revised early milestones. It governs current planning while older feature proposals are refined.

The [assembler requirements](assembler-requirements.md) record the agreed CLI/configuration-file direction and proposed testable M1/M2 behavior.

The [configuration design](configuration-design.md) defines proposed TOML contracts with examples and invalid-input fixture expectations. The three-input separation and TOML choice are agreed; detailed fields remain a proposal.

The [CLI design](cli-design.md) records the four agreed operations and proposed output, exit-code, artifact-identity and reporting contracts.

The [report contract](report-contract.md) and [M1 startup contract](kernel-startup-contract.md) are twice-checked, user-approved implementation baselines; neither is implemented OS behavior.

The [strict schemas and design checks](schemas/README.md) make data constraints executable. The [catalog discovery and process ownership design](catalog-and-process-design.md) records the remaining twice-reviewed P2 choices, now approved.

The [two-pass verification/publication review](verification-publication-review.md) records source checks, an isolated Windows publication experiment, failure scenarios and the revised policy confirmed by the user.

The [assembler architecture](assembler-architecture.md) records agreed component ownership, interface responsibilities, and the normal integration sequence.

The [workflow and failure policy](assembler-workflows.md) records agreed failure, cancellation, artifact-preservation, and cleanup behavior. The dashboard's [planning register](tracking.json) exposes decisions, open gaps, requirements, milestones, workflow steps, tool readiness, and recorded runs alongside the original subsystem register.

## Working agreement

Follow the [agreed priorities and two-item limit](priorities.md). The [plan reevaluation](plan-evaluation.md) records which gaps have improved and what still blocks implementation readiness.

The M1 environment is selected and probed: see the [environment verification record](m1-environment-verification.md). This does not establish a working RustOS kernel.

Every feature progresses through requirements, analysis, design, review, documentation, implementation, and verification. These stages can overlap; approval and completion must be recorded separately. A written proposal is not an approved design. A build is not a verified hardware boot.

The progress register is the source of truth for reported stage status. Specifications are the source of truth for intended behavior. Test output and review records provide evidence. Update these together when work advances.

The [P2 completion and P3 handoff](p2-handoff.md) summarizes the frozen design scope, checks and remaining implementation obligations.

The [P3 verification record](p3-verification.md) documents the implemented Rust host inspector, two acceptance passes and remaining delivery scope. Use the [host-tool instructions](../tools/assembler/README.md) to inspect a configuration.

The [P4 verification record](p4-verification.md) documents real RustOS emulator boots, panic/exception checks and raw evidence. The [P5 build record](p5-build-verification.md) documents snapshot compilation and manifest publication, extending the [Windows process foundation](p5-process-verification.md). The [verifier candidate](p5-verification.md) adds owned QMP checks, external reports and automatic dashboard ingestion; it uses approved emulator profile 0.1.1, with [M1 acceptance complete](m1-acceptance.md). Physical-board images remain pending.
