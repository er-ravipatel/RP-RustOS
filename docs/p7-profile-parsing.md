# P7 typed Pi profile parsing

2026-11-01. Added explicit profile-version dispatch in [the host assembler](../tools/assembler/src/target_profile.rs), the approved [Pi profile](../profiles/rpi-zero2w-a53.toml) and an [inspection configuration](../rustos-zero2w.toml).

Only profile loading accepts versions 1 and 2. User configuration, catalog and existing recipe gates remain schema 1. Version 1 still deserializes the strict M1 emulator structure; version 2 deserializes closed Pi structures. The Pi contract checks target, board module, boot bounds, core count, recipe/method identifiers and the exact D19 asset-lock hash. Unknown/nested fields, changed memory/board/asset identities and unsupported versions fail.

Valid Pi metadata then returns `TARGET_BACKEND_PENDING` before catalog resolution or execution. The actual CLI records failed inspection with readiness unestablished (`null`), no result, no output files and no runtime index. It explicitly states that asset bytes were not checked. Metadata parsing does not establish full configuration validation, module resolution, a build, packaging or hardware support. The installed profile's comment and example configuration make this limit explicit.

## Verification

All 39 host tests pass: 9 unit tests (including four new profile tests), 19 inspection tests (including the new Pi readiness rejection) and 11 Windows process tests. Five existing black-box M1 CLI tests pass. Clippy passes with the two already documented M1 exclusions (`result_large_err`, `uninlined_format_args`). Formatting passes.

The [actual Pi CLI outcome](evidence/p7-pi-profile-inspection.json) was captured and independently checked against the Python profile schema. No Pi output directory was created. M1 diagnostic-code compatibility is covered by existing tests.

A parallel-test run exposed timestamp-only fixture-directory collisions on Windows. Fixture names now include a per-process atomic counter as well as PID/time; the regression suite passed after this correction. No production run-ID or process-control code was changed by that fixture fix.

## Remaining work

Implement real Pi-aware module/board selection and source readiness, then reviewed startup, GPIO/mailbox and console preparation. Keep backend rejection in place until a coherent supported path exists. Stable lock/asset consumption, SD packaging, report generation and physical capture remain later integration work. The current shared kernel still builds only its QEMU BSP.
