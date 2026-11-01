# M2 target selection and evidence contract proposal

2026-11-01. Direction approved by the user as D18. This defines the extension direction; executable JSON schemas and positive/negative fixtures must be completed before implementation is considered ready.

## Compatibility and target selection

Keep the accepted M1 configuration, profile 0.1.1, manifest and report schema 1 valid under their existing strict reader. Do not add optional Pi fields to the M1 emulator structure or reinterpret old reports. Dispatch explicitly by schema version; unknown versions and fields fail closed.

Use profile schema 2 for `rpi-zero2w-a53`, initially version 0.1.0. Retain the user configuration's existing target/features/output selection. Profile 2 has common identity, architecture, Rust target, base modules and supported features, plus a tagged target-specific object. For this target its kind is `raspberry-pi-zero2w`; its closed payload identifies the agreed boot contract, firmware lock, packaging recipe and supported verification methods. It must not accept an emulator object, arbitrary register overrides, shell commands, URLs or executable paths from user configuration.

Resolve exactly one board module and its compatible architecture/kernel/console dependencies. Keep the logical kernel module shared; select one mutually exclusive Cargo board feature and corresponding BSP dependency, entry assembly and linker script. Reject zero boards, mixed boards, unknown selections and mismatched source layouts before compilation. A profile is data used by trusted backends, not permission to execute arbitrary build commands.

Asset acquisition is an explicit preparatory step using repository-reviewed immutable URLs and expected hashes. Normal build uses a verified local asset cache and fails on missing or changed bytes; no implicit network fetch. Pin all required asset licences in the lock as well as boot files. Snapshot consumed lock/config/profile/catalog/source bytes under existing stable-input and no-overwrite rules.

## Manifest and verification versions

M2 manifests use schema 2 with explicit target kind and packaging recipe identity. Preserve source, tool and module provenance. Record each artifact's id, variant, role, safe relative path, byte length and SHA-256. Roles distinguish ELF, flat kernel and SD image. Require exactly one of each role for each normal/panic variant, with explicit image-to-kernel relationships and boot-content inventory. Record every contained boot file's path, size, hash and origin, including generated config and licence files. No hardware pass belongs in an immutable build manifest.

Use separate trusted recipe identities for image inspection and physical serial capture. `verify` on a Pi bundle defaults to image inspection and reports scope `image`; it never silently opens a serial port or claims hardware success. Physical capture is explicit, for example `verify --method hardware --session <file>`. This syntax is proposed and must receive strict CLI fixtures before use. Existing M1 verify behaviour remains unchanged.

Reports for these methods use schema 2. Common fields identify operation/method, run, terminal status, manifest hash, exact artifact identities, timestamps, diagnostics, hashed evidence and owned-resource cleanup. Use closed method-specific payloads:

| Method | Required evidence | Success means |
| --- | --- | --- |
| Image inspection | Both image identities; geometry, names, allocation and extracted-content checks; inspector version; per-image result | Both disk images match the declared package contract |
| Hardware capture | Board identity, adapter/port/settings, image variant/hash, operator media/power-cycle declaration, fresh per-scenario capture boundaries, bounded serial logs, exact markers and cleanup | Both physical startup and deliberate-panic scenarios satisfy the capture recipe |

Hardware session input is strict structured data, not a command script. Port opening is exclusive and capture starts before the operator-triggered boot. Pre-existing buffered data is discarded and the serial device is bounded and closed on every terminal path. Scenario limits, re-arm prompts and capture bounds belong in the trusted recipe, not unrestricted session overrides. A wrong-variant marker, truncated line, error marker, disconnection or timeout cannot pass. Repeat/replayed logs are never imported as a newly observed run.

Operator declaration binds the claimed flashed image to the session; serial markers alone cannot cryptographically prove which SD bytes executed. Reports must state that limitation. Record media preparation/read-back evidence when available. The verifier owns its serial handle and helper processes; board power removal is recorded as an operator action, not fabricated process cleanup.

## Dashboard integration

Keep execution-index schema 1 for historical outcomes. Introduce a versioned schema-2 index with explicit method/report binding for M2. The importer must dispatch strictly, validate all artifact/log relationships and render `image` separately from `hardware` and `emulator`. Unsupported or invalid entries show import errors. Terminal outcome refresh remains the current behaviour; do not advertise streaming in-flight progress.

Do not relax the M1 pass predicate to accommodate physical tests. Hardware capture must not invent QMP stop requests or `processes_settled` for a board. Image inspection must not satisfy a requirement for physical boot. Schema/importer/browser fixtures must exercise each distinction.

## Two review passes

1. Current-code audit: Profile unconditionally requires Emulator; profile_valid enforces the M1 target; build.rs restricts source layouts; the kernel depends directly on the QEMU BSP. Manifest, verify, execution index and dashboard importer currently enforce M1-shaped records. Therefore a new TOML profile alone is insufficient, and changing a scope label is unsafe.
2. Compatibility/failure walkthrough: preserve old M1 schema fixtures; reject unknown v2 fields/versions, mixed boards, missing locked assets, swapped normal/panic roles, bad extracted hashes, image-as-hardware claims, stale capture and incomplete cleanup/report publication. Require new readers to inspect v2 before publishing it. M1 regression tests plus separate v2 contract, package and capture tests gate completion. These are Codex self-review passes, not completed implementation tests.

Decision D18: user approved strict versioned target/manifest/report extensions, exactly one board selection, offline locked builds and separate image-inspection versus explicit hardware-capture methods on 2026-11-01. Concrete schemas/fixtures, asset licences and hardware setup remain P6 exit work.
