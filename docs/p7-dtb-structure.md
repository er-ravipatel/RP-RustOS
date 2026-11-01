# P7 bounded DTB structure validation

2026-11-01. Resumed the interrupted structure-parser work and resolved its failing real-file check.

The [nonrecursive parser](../bsp/rpi-zero2w/src/structure.rs) checks root/node hierarchy, property placement and lengths, string-name bounds, duplicate property names (including different string offsets), zero padding and exact final termination. It reuses the header/reservation preflight. Limits are 16 nested nodes, 256 properties per node, 128-byte names and 16,384 tokens. It does not interpret RAM, board compatibility or reserved-memory properties.

The interrupted run's 64-property limit rejected the real candidate's `/__symbols__` node. An independent host inspection found 159 properties in that node, maximum depth 5, 1373 tokens and maximum name length 29. The limit is now 256, with regression cases at 160, 256 and 257 properties. Duplicate-name detection uses compact u32 offsets rather than fat pointers; tests keep frame storage below 20 KiB. This measures frame storage, not the complete runtime stack footprint.

All 13 BSP tests pass. AArch64 no_std compilation and Clippy pass. The [pinned real-file structure check](evidence/p7-pi-dtb-structure.json) also passes at a synthetic physical address; no actual firmware handoff address was observed. The existing source and asset bytes were not changed.

This checks bounded token structure, not all Devicetree semantic rules or usable physical RAM. Next: interpret the board compatibility and RAM/reserved-memory properties, then review the stackless entry preflight and CPU transition before kernel wiring. Pi boot remains unavailable.

Reference: [Devicetree flattened-format specification](https://devicetree-specification.readthedocs.io/en/stable/flattened-format.html). The initial reference/header checks and second independent real-file/boundary checks remain separate from physical-board acceptance.
