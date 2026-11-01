# P7 typed Pi input preparation and source attribution

2026-11-01. The assembler now resolves the actual Pi kernel sources into a separate typed input description. Pi snapshot compilation/image publication is not enabled yet.

## Source model

The [catalog](../catalog/modules.toml) now gives the logical kernel module an explicit source_overrides entry for rpi-zero2w-a53 pointing at bsp/rpi-zero2w/kernel. Its fallback remains core/kernel for M1. This is an optional, typed catalog field; existing schema-1 catalogs without it retain their previous behavior. Unknown fields still reject. Every override target must belong to that module's declared targets and every path passes the existing safe-relative/link/reparse checks, including overrides for currently unselected targets.

Source inspection uses the effective target mapping for Cargo manifests, source presence, input hashing and output/source overlap protection. A present Pi kernel manifest must name rustos-pi-kernel; an M1 package cannot be attributed as that kernel. The Pi BSP dependency edge now includes console-pl011 as well as hal, matching its real clock-helper dependency.

The [Pi preparation type](../tools/assembler/src/pi_build.rs) accepts a PiProfile rather than the emulator profile type. It records the actual kernel manifest/package, target, effective module source ownership, normal/panic feature sets and unique snapshot roots. Nested kernel/BSP trees are attributed separately but the kernel is copied once through its BSP parent. For the reviewed four-module baseline, roots are bsp/rpi-zero2w, drivers/console and hal. Entry-only is excluded from both artifact feature sets. These are validated input descriptions, not claims that a snapshot has been created or compiled.

The M1 execution backend's frozen four-layout check now compares effective mappings as well, preventing an M1 override from silently changing the compiled-source layout. Default M1 source paths remain unchanged.

## Verification and scope

[38 Rust assembler tests pass](evidence/p7-pi-source-preparation.json), including actual Pi manifest selection, nested-root deduplication, wrong package/M1 attribution rejection, unsafe paths, unknown override targets, missing modules and preserved pending status. The [actual read-only Pi CLI check](evidence/p7-pi-source-preparation-cli.json) reports its real kernel manifest and TARGET_BACKEND_PENDING without creating a bundle.

Five M1 CLI tests and nine M1 build acceptance tests pass after the catalog/inspection change, including independent boot of newly assembled development artifacts, snapshot hashes, dependency escape rejection, no replacement of existing bundles and retained failed staging. They used a unique test-owned output directory; the original immutable M1 bundle was not replaced.

Strict all-target Clippy exposed the project's existing large Diagnostic/error-result design (also used by the new preparation method). A scoped run allowing only clippy::result_large_err passes with every other warning denied. A nearby diagnostic formatting warning was corrected. This is not claimed as an unqualified strict Clippy pass.

First review checked effective source attribution and typed target separation. Second review checked hostile override inputs, M1 layout protection, snapshot-root deduplication and the actual no-output CLI path. Both are self-review.

## Next implementation boundary

Implement an immutable Pi source snapshot and offline/locked two-variant compilation using the typed description, including actual Cargo workspace/dependency closure and tool provenance. Shared HAL/console manifests must compile in the isolated Pi snapshot without importing an unselected M1 workspace accidentally. Recheck source stability, linker/load/stack contracts and variant feature identity on the resulting artifacts.

Only then connect flat kernels, locked firmware/source notices and both complete images to schema-2 publication and independent inspection. The public Pi backend remains gated until it can publish a complete valid bundle; complete_bundle_ready is explicitly false. No firmware bytes were checked by this preparation-only path, no Pi build output was published and no physical media was touched.
