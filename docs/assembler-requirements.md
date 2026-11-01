# OS assembler requirements — initial proposal

## Agreed interface direction

The first version uses a configuration file and command-line interface. A graphical configuration interface is deferred. This direction was agreed on 2026-10-31. The M1 requirements now have [implementation, review and acceptance evidence](m1-acceptance.md); ASM-010/011 remain M2 proposals. The design discussion below preserves the original requirement baseline.

## Proposed configuration contract

The configuration identifies its schema version, target profile, and requested OS features. Architecture, mandatory drivers, supported output formats, and boot assumptions come from the target profile. TOML and separate user/profile/catalog inputs are agreed. See the [schema proposal](configuration-design.md) for detailed fields, example IDs, readiness diagnostics and fixture expectations; these details still require review. CLI spelling remains a design decision.

## Proposed requirements and acceptance checks

| ID | Required behavior | Acceptance check | Milestone |
| --- | --- | --- | --- |
| ASM-001 | Read a versioned configuration and reject malformed data, unknown fields, unsupported versions, and unknown targets/features | Run fixtures for each case; report the offending field and reason, return nonzero, and do not start compilation | M1 |
| ASM-002 | Resolve required modules and explain why each module was selected | A valid minimal profile produces a resolved plan listing requested and automatically required modules, with dependency reasons | M1 |
| ASM-003 | Reject incompatible modules, dependency cycles, and unavailable required modules | Invalid fixtures identify the conflicting modules or cycle and fail before compilation | M1 |
| ASM-004 | Provide validation and plan inspection without compiling or packaging | The inspection command emits the resolved plan; no build subprocess is invoked and no OS artifact is produced | M1 |
| ASM-005 | Build selected components using recorded toolchain and input versions | A documented clean setup produces the expected kernel artifact; tool failures return nonzero with the failing step and diagnostic | M1 |
| ASM-006 | Produce a machine-readable manifest describing the configuration, resolved modules, source revisions or hashes, tool versions, and artifact hashes | Inspect a successful result; manifest entries match actual selected inputs and generated artifact hashes | M1 |
| ASM-007 | Validate output paths, preserve source inputs, and prevent a failed run from being presented as a successful result | An existing destination is rejected by default; interrupted or failed runs leave no success marker and identify any partial output | M1 |
| ASM-008 | Run emulator verification with bounded execution and separate startup and deliberate-panic checks | Verify expected markers for each scenario; missing markers, unexpected process termination, or timeout fail the relevant check and return nonzero | M1 |
| ASM-009 | Report build, packaging, and verification outcomes separately, including skipped verification | Build-only execution reports verification as not run; a verification failure remains visible even when compilation succeeded | M1 |
| ASM-010 | Package a Zero 2 W profile into a bootable SD-card image with identified boot assets | Inspect image contents and manifest, then capture startup and panic output on the physical board using a recorded procedure | M2 |
| ASM-011 | Keep image creation separate from writing physical media | Image assembly does not write to a physical disk; M2 documents a separate media-writing procedure | M2 |

Reproducible initially means repeatable documented production of the expected artifact type and behavior using identified inputs. Byte-identical output is a separate property requiring an explicit future acceptance criterion.

## Required result records

Additional acceptance proposals ASM-012 through ASM-015 cover failure propagation, retained unverified artifacts, cancellation, and dashboard visibility in the [workflow policy](assembler-workflows.md).

Each run reports the selected target, resolved configuration, step outcomes, artifact locations, applicable hashes, and verification outcomes. Failed runs retain useful diagnostics with an explicit failure result. A report must not label a target hardware-verified based on emulator evidence.

## Open design decisions

- Configuration syntax and schema; CLI command names and structured error format.
- Emulator machine, version policy, invocation, startup markers, and timeout values.
- Target/module metadata schema, compatibility rules, and dependency-resolution algorithm.
- Supported initial development environment and tool installation procedure.
- Artifact directory layout, atomic publication behavior, and failure-report format.
- Firmware sourcing, version identification, and image-layout details for M2.

## Review and traceability

The [M1 acceptance record](m1-acceptance.md) names the implementation self-reviewer, findings/dispositions, test procedures, limits and per-requirement evidence. The dashboard links M1 implementation and test files. M2 requirements need their separate hardware design and review; no physical-board acceptance is inferred.
