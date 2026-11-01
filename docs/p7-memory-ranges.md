# P7 declared-memory range checks

2026-11-01. Added bounded no_std [memory-range validation](../bsp/rpi-zero2w/src/memory.rs). It consumes explicitly supplied RAM/reserved ranges and DTB placement; it does not extract properties from the DTB or access physical memory.

The checks reject empty/overflowing/out-of-board ranges, overlapping RAM declarations and reservations, a reserved byte in the complete kernel budget, DTB/kernel overlap, and incomplete containment of either object in declared RAM. Counts are bounded to 16 RAM ranges and 128 reservations. For this conservative M2 path, each complete object must fit one declared RAM bank; adjacent banks are not silently merged. A DTB may itself be listed as reserved, because these checks do not write it.

Six new host tests cover valid low-memory/DTB reservations, arithmetic bounds, one-byte partial containment, exact-touching versus overlapping boundaries, duplicates and excessive counts. All 19 BSP tests pass. AArch64 no_std compilation, formatting and Clippy pass. This crate remains isolated from the accepted M1 kernel workspace.

This is validation of supplied declarations, not detection or authentication of usable hardware RAM. A complete boot-data path still needs board compatibility checks, address/size-cell decoding, memory and reserved-memory property extraction, header reservations and handling of unsupported/dynamic reservations. None of those may be omitted before this checker is used as part of a boot decision. The firmware can also update the static DTB before handoff; a repository DTB file is not an observed runtime memory map.

Next: connect validated DTB properties to this range checker, then review and implement the stackless handoff/CPU transition before kernel wiring. No Pi boot or writable-memory authorization is claimed by this slice.
