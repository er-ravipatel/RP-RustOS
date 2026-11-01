# P7 Zero 2 W BSP foundation

2026-11-01. Added an isolated no_std [Pi BSP crate](../bsp/rpi-zero2w/Cargo.toml) with the approved kernel reservation and a bounded [DTB preflight parser](../bsp/rpi-zero2w/src/lib.rs). It is not connected to the kernel and does not initialize CPUs, clocks, GPIO or UART. M1's four-member workspace remains unchanged.

The parser takes an already-readable slice and its claimed physical placement; it never dereferences a physical pointer. It validates header version/size, block bounds/alignment/order, reservation-table termination, a 128-entry limit, overlapping/overflowing reservations and collisions with the kernel budget. Placement must be aligned, outside low firmware/kernel space and below a conservative board addressability ceiling. This ceiling does not prove usable ARM RAM.

Six host tests pass, including every truncation of a synthetic DTB, malformed header fields, pointer bounds, reserved-range conflicts and the count limit. AArch64 no_std compilation and Clippy pass. The [real pinned DTB file check](evidence/p7-pi-dtb-preflight.json) passes at the explicitly synthetic address 0x1000000; it reports 33,724 bytes and one reservation. This is a host file preflight, not observed firmware placement or hardware output. Nine existing M1 build acceptance tests and the approved real asset-lock byte check pass.

The current CLI now finds the BSP's basic source files but still returns `TARGET_BACKEND_PENDING` and says kernel board wiring is unimplemented. A source package existing is not evidence of a bootable target.

The first review used the [official DTB format specification](https://devicetree-specification.readthedocs.io/en/stable/flattened-format.html). The second exercised malformed/boundary inputs and inspected the real candidate file. Full tree-token/property parsing, usable-memory/reserved-memory nodes and board compatibility remain to be checked before boot information can be trusted. This helper alone must not authorize writable kernel memory.

Startup integration must also resolve the stackless handoff preflight before private stack/BSS writes. A normal Rust function can use a stack, so this library is not a substitute for that assembly-stage safety gate. Exact EL2-to-EL1 register review, linker/entry wiring, mailbox/GPIO/UART preparation and physical acceptance remain pending.
