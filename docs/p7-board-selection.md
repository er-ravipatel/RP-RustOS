# P7 shared module resolution and board selection

2026-11-01. M1 and Pi profile inspection now share one catalog validation/dependency-resolution implementation. The portable module metadata no longer requires the QEMU BSP directly; each profile selects its own board. Catalog metadata lists the planned Pi BSP separately and rejects incompatible targets and selected conflicts. Exactly one selected module must have BSP ownership.

The Pi path resolves `hal`, `bsp-rpi-zero2w`, `console-pl011` and `kernel`, then stops with `TARGET_BACKEND_PENDING`. It does not check Pi source readiness or boot-asset bytes, produce a successful plan result or compile a Pi kernel. The current kernel Cargo dependencies and assembly still implement the QEMU path only. Catalog compatibility here is planned module metadata, not a hardware-support claim.

The [real CLI evidence](evidence/p7-board-selection.json) shows M1 still produces its four-module plan with readiness false, and Pi resolves its own board before explicit backend rejection. The previous [profile-only evidence](p7-profile-parsing.md) is an earlier checkpoint; resolution now extends beyond it.

Verification: all 41 host tests pass (9 unit, 21 inspection, 11 Windows process), including Pi module selection and explicit missing/mixed-board rejection. All five existing M1 CLI tests and nine M1 build acceptance tests pass. Build evidence is retained under `target/p5-build-1793485303655152100`. Clippy passes with the previously documented exclusions. The negative-test edit helper normalizes CRLF for multiline substitutions; production parsing still consumes original bytes.

No Pi BSP source or image has been introduced. Next: board source readiness and the reviewed Pi entry/initialization implementation. The [hardware inventory](m2-hardware-setup.md) now records both cards, reader, photographed power adapter, header availability and missing serial adapter. Physical tests remain pending; no media-erasure permission has been inferred.
