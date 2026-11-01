# P7 bounded memory tuple decoding

2026-11-01. Resumed after the power interruption; the prior board validation remained intact.

Added `decode_reg` to the isolated Pi BSP. It decodes big-endian address/size tuples with explicit parent cell counts of one or two each, using caller-owned bounded storage. It validates every tuple before changing output. Empty and truncated properties, unsupported cell widths, excess ranges, zero-sized ranges, arithmetic overflow and addresses beyond the board ceiling fail explicitly.

Validation: all 24 BSP host tests passed; AArch64 no_std compilation and Clippy with warnings denied passed. New tests cover all four cell-width combinations, multiple banks, malformed properties and unchanged output after a later invalid tuple.

This is a tuple decoder, not a complete firmware memory-map validator. Parent-cell extraction, node identity/status, memory and reserved-memory collection, header reservation integration and explicit rejection of unsupported dynamic reservations remain pending. The static pinned DTB's zero-sized memory placeholder cannot establish usable RAM. No physical-memory access, Pi boot or SD card operation occurred.

Next: integrate decoding with bounded tree traversal and the existing containment/conflict checks, then validate the complete path with synthetic firmware-updated DTBs. Stackless startup and kernel wiring remain pending.
