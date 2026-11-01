# M2 dynamic reservation and startup review

2026-11-01. Decision D20 approved by the user after the Redox research review. The following records the reviewed design baseline. Its bounded Rust CMA validation/selection is now implemented; see the [implementation evidence](p7-cma-reservation.md). Stackless entry remains pending.

## Recommendation

Honor the known `/reserved-memory/linux,cma` dynamic request by reserving a deterministic physical pool from firmware-declared usable ARM RAM. Do not enable DMA, a Linux allocator, display or camera services. Keep the pinned DTB, firmware and approved asset lock unchanged.

Initially support only one active dynamic node at this exact path with exact `shared-dma-pool` compatibility, empty `reusable` and `linux,cma-default`, a valid positive `size`, no `reg`, no `no-map`, no alignment or allocation-range constraints, and no unknown semantic properties. Permit only an inert, correctly encoded optional phandle in addition to these properties and an accepted status. Other dynamic requests remain unsupported. The pinned file currently requests 64 MiB. Do not assume firmware leaves the node unchanged: validate the actual handoff tree.

Choose a 4 KiB aligned pool by a bounded, deterministic search from highest usable address downward, requiring the complete pool to fit one RAM bank. Exclude the entire kernel budget, the full DTB, low memory below 0x1000, all static tree reservations and every header reservation. Check all arithmetic and the combined reservation-count limit. Validate candidates at bank ends and exclusion boundaries rather than scanning individual addresses. Treat the selected pool as reserved and unavailable even though M2 has no consumer. Reject insufficient space; never shrink or silently omit the request. The alignment is RustOS policy for this unconstrained request, not a firmware guarantee.

The final map must pass the same containment/conflict rules as static reservations. Record the selected pool in boot diagnostics after console initialization. Host tests must prove deterministic selection independent of declaration order, boundary alignment, no-space failure, DTB/kernel/static/header avoidance, malformed requests and rejection of unsupported variants. Do not claim the static repository DTB is boot-ready: its RAM placeholder still needs firmware updates.

## First review: source semantics

The [reserved-memory binding](https://github.com/devicetree-org/dt-schema/blob/main/dtschema/schemas/reserved-memory/reserved-memory.yaml) distinguishes an addressed `reg` reservation from a dynamic `size` request. Its optional alignment and allocation-range constraints cannot be ignored by a general allocator; this proposal rejects those variants. Reserving a pool satisfies the request without introducing any driver that consumes it. This is a RustOS design inference from the binding, not a Pi firmware guarantee.

The [published Pi stub](https://github.com/raspberrypi/tools/blob/master/armstubs/armstub8.S) enters EL2, supplies the DTB pointer in x0 and parks secondary cores. This supports the existing D16 direction but does not prove the behavior of the pinned firmware binary on the user's board. No new register masks are approved by this review.

## Second review: implementation and failure cases

Inspected the current tree walker, board checks, tuple decoder and range validator against D16. They operate on readable slices using a stack. Calling them before proving stack safety would violate D16. The dynamic allocator also must not write its result into an unvalidated stack or BSS.

Therefore preserve the order: primary-core/EL/cache-state checks; register-only bounded DTB and RAM/reservation preflight; proof that the complete kernel budget is writable and disjoint from DTB/reservations; only then establish the private stack and run the full Rust checks, including dynamic pool selection; only after success initialize BSS and board buffers. Assembly preflight can reject all unhandled layouts and defer dynamic allocation because that request has no physical placement yet; it must still validate the request shape and protect all addressed reservations. Failure parks silently before UART, with bounded host capture treating silence as failure.

Before implementing entry, specify exact register ownership, bounded loops, scratch use, EL2-to-EL1 masks and barriers, and test the assembled code with an emulator harness and disassembly. Require agreement between assembly preflight and the Rust checker on accepted fixture trees. No scratch stack or advertised-total-RAM fallback is allowed. Both review passes are self-review, not independent review or hardware evidence.

## Scope and remaining limits

D20 would authorize the narrow dynamic pool policy and the above startup sequencing refinement. It does not mark M2 complete, approve exact CPU register values, change the asset lock, authorize card erasure or assert that QEMU emulates Zero 2 W firmware/peripherals. Physical acceptance still needs the deferred UART/GPIO setup.
