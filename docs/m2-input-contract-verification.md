# M2 profile/asset input contract checks

2026-11-01. P6 design evidence only. D18 direction is agreed; the assembler still supports its M1 runtime contracts only.

Added a closed schema-2 Pi profile and firmware-lock schema in [m2-inputs.schema.json](schemas/m2-inputs.schema.json), generated and semantically checked by [the design utility](../tools/m2_input_contracts.py). The profile fixes approved boot bounds and one active core, names repository recipe identifiers, and binds exact lock bytes. Asset checks enforce immutable commit/path URLs, required boot files, unique names/IDs, correct roles and explicit licence-record relationships.

First pass: schema validation plus fixtures for the valid profile/lock, changed boot assumptions, mixed boards, unknown keys/versions and wrong types. Second pass: cross-record checks for commit/URL mismatch, case collisions, missing/wrong asset roles, missing/recursive licence references, unsafe Windows paths and changed lock bytes. All 12 test methods pass. Existing M1 design and dashboard checks were also rerun separately.

The fixtures are [explicitly synthetic](examples/m2-contracts/README.md); no execution runs were added. Hash formatting and licence references do not establish actual asset contents, licence correctness or trust. The checker does not acquire assets, resolve real filesystem identities, implement the Pi backend or inspect images.

Remaining P6 work: manifest/report/index schema-2 contracts and semantic fixtures; real firmware/device-tree licensing inventory; hardware setup information; implementation-level architecture/peripheral review. P6 and M2 remain in progress.
