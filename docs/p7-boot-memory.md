# P7 integrated DTB memory validation

2026-11-01. Added a bounded event walker and `validate_boot_memory` to the isolated Pi BSP. It validates board identity and the complete tree, reads explicit root address/size cells, collects active root memory nodes and static reserved-memory children, includes header reservations, and applies the existing kernel/DTB containment and conflict checks. Collected data has no physical side effects and is discarded on error.

The conservative policy supports one or two address/size cells, requires reserved-memory cells to match the root with empty `ranges`, and accepts missing/okay/ok status or skips disabled nodes. Unknown status, nested memory/reservation children, unsupported mappings, dynamic size/alignment/allocation requests, and simultaneous no-map/reusable flags fail explicitly. Overlapping reservations, including overlaps between header and tree declarations, are rejected rather than merged. Arrays remain bounded to 16 RAM banks and 128 combined reservations.

Validation: 29 BSP host tests, AArch64 no_std compilation and Clippy with warnings denied pass. Synthetic trees cover successful RAM/static/header reservations, incomplete containment, zero-sized RAM, disabled memory, unknown status, missing cells, reserved kernel bytes, overlapping reservations and dynamic allocation rejection. The unchanged pinned 33,724-byte DTB still passes board/structure checks but returns `DynamicReservation` from the integrated validator because of its CMA node. Its separate zero-sized memory placeholder also cannot establish usable runtime RAM.

This policy intentionally leaves real firmware handoff acceptance unresolved: dynamic CMA handling must be reviewed and tested before boot wiring. The function requires an already-readable slice and safe stack. It does not implement stackless preflight, authenticate firmware, authorize physical writes or demonstrate a Pi boot. The accepted M1 workspace remains unchanged.

Next: review the dynamic CMA policy and firmware handoff assumptions twice, then design the stackless safety checks and CPU entry sequence. No card flashing or hardware action is required yet.
