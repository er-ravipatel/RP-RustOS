# Assembler configuration design — schema 1 draft

## Decision and review boundary

Agreed on 2026-10-31: TOML; separate user configuration, target profiles and module catalog; repository-local profiles/modules with explicit versions. External module downloads and graphical selection are deferred. Field contracts and their strict schema/fixture reconciliation form the P2 design baseline. The parser/resolver and M1 assembly/verification are implemented; see [current acceptance](m1-acceptance.md).

## User configuration

See [minimal example](examples/m1.toml). Exact required keys are `schema_version` (integer 1), `target` (registered identifier), `features` (nonempty array of distinct registered feature IDs), and `output_dir` (nonempty relative path). Unknown keys, wrong types and duplicate TOML keys are errors. Identifiers match `[a-z][a-z0-9-]*`.

`output_dir` resolves relative to the configuration file's directory, not the shell's current directory. Reject absolute, drive-qualified, UNC, device and parent-traversal paths; reject source-root overlaps and paths escaping the output root through links. An occupied final destination is rejected for assembly. Inspecting a plan neither creates nor requires an empty destination. Concrete Windows path identity and publication checks remain implementation design work.

The user cannot override CPU, architecture, driver addresses or boot format in this schema. Select another target profile to change hardware assumptions. Verification execution is a CLI operation selection; it does not silently change the requested OS features.

## Target profile

See [emulator profile](examples/qemu-virt-a53.toml). Required keys:

| Field | Type / constraint | Meaning |
| --- | --- | --- |
| `schema_version` | integer 1 | Metadata schema version |
| `id`, `version` | identifier, exact version string | Profile identity; versions are local declarations, not resolved release claims |
| `architecture`, `rust_target` | recognized target strings | Compilation architecture/ABI |
| `base_modules` | distinct module IDs | Always required modules |
| `supported_features` | distinct feature IDs | Features this profile permits |
| `artifact_format` | `elf` for M1 | Kernel output format |
| `emulator` | table | Fixed QEMU machine, CPU, memory, cores, accelerator and version policy |
| `verification` | table | Verification scope and registered recipe identifier |

The emulator table requires `qemu_version`, `machine`, `cpu`, `memory_mib`, `cores`, `accelerator`, `instruction_counting`, `secure`, `virtualization`, and `gic_version`. Profile 0.1.1 requires `instruction_counting = "auto"`, approved on 2026-11-01 after Windows QMP checks; it maps to `-icount shift=auto`. Versions match the selected tested release; accepting other settings requires explicit profile revision and verification. The verification table requires `scope = "emulator"` and `recipe = "startup-and-panic-v1"`. Its normal/panic RustOS artifacts and bounded verifier are now implemented; see [current evidence and remaining acceptance](p5-verification.md).

QEMU executable paths are local tool configuration, not portable target metadata. Do not permit arbitrary shell-command templates in profiles. Parse typed settings and construct subprocess arguments without shell interpolation. ELF entry and linker layout belong to a separate reviewed startup contract, not user configuration.

## Module catalog

See [catalog example](examples/modules.toml). Required root keys are `schema_version`, `modules`, and `features`. A module record requires `id`, `version`, `kind`, `source_dir`, `architectures`, `targets`, `requires`, and `conflicts`. Kinds are `kernel`, `hal`, `bsp`, or `driver` initially. `source_dir` is repository-relative, with no external paths or traversal. Architecture/target lists declare compatibility. Dependency/conflict lists contain module IDs. Reject duplicate IDs, missing dependencies, self-dependencies, cycles and selected conflicts.

A feature record requires `id` and `requires` (module IDs). Each supported feature must have exactly one definition. Every selected module must support the target and architecture. The catalog offers one exact version per module ID initially; no version solver or download mechanism is implied. Manifest content hashes and revisions identify actual inputs beyond declared versions.

Example module entries describe planned source directories. The current repository lacks crate manifests and source implementations. Metadata-only plan inspection may describe a coherent selection, but must state `build_ready = false` and list missing inputs. Build prerequisite checks reject missing manifests/source before compilation. An unknown module ID is a resolution error; registered metadata with missing implementation is a separate prerequisite error. This distinction refines ASM-003 without claiming planned modules are available to build.

## Proposed resolution contract

1. Parse and validate all input schemas and identifiers.
2. Look up target, reject unsupported features and inconsistent metadata.
3. Start with target base modules plus requested feature dependencies.
4. Expand dependencies; record all direct selection reasons, not just the first.
5. Reject unknown dependencies, cycles, incompatible modules and conflicts. A conflict declared by either selected module is sufficient.
6. Emit stable dependency-first ordering; use lexicographic IDs to break ties.
7. Include exact metadata identities, selected/requested features, module versions, reasons, readiness diagnostics, artifact type and verification recipe in the resolved plan.

The minimal example should select `hal`, `bsp-qemu-virt`, `console-pl011`, and `kernel`. Dependency-first ordering is `hal`, `bsp-qemu-virt`, `console-pl011`, `kernel` for this graph. All are required by the combined base/feature selection. Explanations retain each edge. This is an expected result, not output from an implemented resolver.

## Error and fixture contract

See [fixture expectations](examples/fixture-expectations.json). Proposed errors identify `code`, `input`, `field` or dependency chain, and `message`. Unknown keys and versions fail without compilation. Validate/inspect failures return nonzero; exact numeric exit codes and CLI command spelling remain to be specified.

Fixtures cover malformed TOML, unknown key, unsupported schema, unknown target, unsupported feature, missing module, dependency cycle, selected conflict, incompatible architecture and unsafe output. Catalog mutation cases apply only to disposable fixture data, not the repository catalog. They define P3 acceptance scenarios; no resolver assertions have run.

## P2 completion and implementation handoff

The four operations validate/plan/build/verify are now agreed. See the [CLI and result proposal](cli-design.md) for their detailed semantics, output and error contracts.

The input/schema, report, startup, repository-discovery and process-ownership design baseline is recorded and checked. Implement the parser/resolver in P3 and execute the structural and graph fixtures. Concrete runtime proof remains implementation work. Proposed numeric CLI exit codes must be reconciled before the public CLI acceptance gate.

P2 is complete as design work: input separation, examples, strict schemas, fixtures, approved report/startup/publishing contracts, and repository/process ownership rules are recorded. See the [handoff](p2-handoff.md). Validation and resolver runtime behavior are P3; no implementation completion is implied.

## Target-specific module sources

The catalog accepts optional source_overrides keyed by a module-supported target. The kernel maps rpi-zero2w-a53 to bsp/rpi-zero2w/kernel while its fallback core/kernel remains M1. Effective paths retain all existing safety/input checks. See the [typed Pi preparation evidence](p7-pi-source-preparation.md); a resolved mapping does not enable complete-bundle execution.
