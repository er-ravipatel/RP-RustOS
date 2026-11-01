# P7 Pi source-prerequisite inspection

2026-11-01. Pi and M1 inspection now share source-layout and output-overlap checks. Each selected module needs a readable Cargo package manifest and a default library/binary source entry. Protected output paths now include the locked asset directory as well as profiles, catalog, recipes, assembler sources and selected source trees.

The [real Pi CLI outcome](evidence/p7-pi-source-inspection.json) identifies the missing Pi BSP source while explicitly preserving `TARGET_BACKEND_PENDING`, readiness unestablished and no generated output. Kernel board wiring and Pi execution remain unimplemented. Finding readable files is only a prerequisite check, not proof that their contents implement a board or that the source graph compiles.

Tests cover malformed Pi Cargo metadata, missing BSP source, a placeholder BSP that must remain unavailable for execution, and output overlap with selected board sources/locked assets. All 44 host tests pass (9 unit, 24 inspection, 11 Windows process). The five M1 CLI and nine M1 build tests pass; build evidence is retained under `target/p5-build-1793485437911041200`. Clippy passes using the two existing exclusions after correcting borrowed-path lint findings from the shared-function refactor.

The CLI still returns no successful Pi plan or image. Asset bytes are not loaded by this inspection path. Next: implement actual board sources and reviewed startup/console wiring, with target compile checks and unchanged M1 acceptance boundaries. Physical testing still requires the deferred UART adapter and GPIO connection.
