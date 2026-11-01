# M2 manifest and report design checks

2026-11-01. Added [schema-2 output definitions](schemas/m2-outputs.schema.json), [semantic validation](../tools/m2_output_contracts.py) and [synthetic fixtures/tests](../tools/test_m2_output_contracts.py). They do not enable M2 in the assembler or dashboard importer.

The manifest identifies exactly six artifacts: ELF, flat kernel and SD image for each normal/panic variant. Semantic checks bind the derivation chain and image kernel inventory, require boot notices, preserve source/tool/module identities, and constrain image size and recipes. Reports have distinct closed image and hardware payloads. Both bind the exact manifest bytes, recipes and image identities.

First pass checks schema structure, correct fixtures, unknown fields/versions, missing notices, swapped variants/derivation, wrong hashes and false image checks. Second pass checks manifest byte changes, wrong scope/recipe, cleanup/error contradictions, missing fresh-boot declarations, wrong markers, reused capture identifiers/logs, unbound logs, reversed/overlapping times, deadline violations and unsafe/colliding paths. All 17 test methods pass. These are two Codex self-review methods, not independent implementation or hardware acceptance.

Hardware fields preserve an explicit limitation: the claimed written image is based on the operator's declaration, not cryptographic device attestation. Unique capture/log identities and timing consistency reject obvious contradictions; they cannot detect maliciously fabricated records. The eventual runner/importer must authenticate actual captured bytes and validate observed markers, errors and resource ownership. This design checker does not open files/devices, inspect disk images, execute firmware or verify serial output bytes.

Additional runtime checks remain required: stable artifact/log file identities and actual hashes, complete content-to-firmware-lock binding, source-package provenance, trusted recipe lookup and numeric budgets, process/serial ownership, exact marker parsing, error detection, atomic reporting and index publication. A schema-shaped pass is not accepted runtime evidence.

Remaining P6 contracts: schema-2 execution indexes and explicit hardware-session inputs/CLI fixtures. The real asset source/licensing package and hardware inventory also remain open. M1 schema-1 behaviour is unchanged.

Reproduce from the repository root with optional design dependencies available:

```text
python tools/m2_output_contracts.py
python tools/test_m2_output_contracts.py -v
python tools/test_m2_input_contracts.py -v
python tools/test_design_contracts.py
```
