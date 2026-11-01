# P7 controlled serial success/failure and deliberate panic

2026-11-01. [Controlled runner](../tools/test_pi_console_controlled.py), [four passing cases](evidence/p7-pi-console-controlled.json). These are explicitly synthetic debugger experiments, not physical or unmodified-firmware success.

## Controlled inputs

The runner loads separate hashed normal and panic-test ELFs behind the test-only reset adapter. It breaks at the existing compiled clock-response parser, checks the operation identity, expected tag and stack snapshot bounds, and verifies the actual argument layout before altering anything. On the third, completed mailbox response it replaces only the local measured-response snapshot length/rate with an eight-byte, 48 MHz result. No production instructions, clock policy or actual firmware-owned buffer are changed. The kernel therefore receives an explicitly synthetic valid measured rate.

For fault cases only, the runner stops at the compiled polling driver boundary, verifies the PL011 object points to the expected UART, then redirects that object's base to a synthetic RAM register page. TXFF is held high to force byte timeout, or BUSY held high to force final-drain timeout. This tests the real bounded polling/error path with controlled register values; it is not an observed hardware UART fault.

## Results

| Case | Observed bytes and terminal |
| --- | --- |
| Controlled normal startup | Exact engineering ready line and console-ready park, marker 0xc011. |
| Controlled TX timeout | No bytes; failure stage 6, marker 0xc10c. |
| Controlled drain timeout | Ready line already transmitted; failure stage 7, marker 0xc10c. Complete bytes alone do not establish successful drain. |
| Controlled deliberate panic | Ready line then exact RUSTOS_PI_DELIBERATE_PANIC line; dedicated park, marker 0xc0de. |

The panic artifact uses the separate panic-test feature and has its own recorded SHA-256. Its deliberate-panic routine receives the initialized console directly and uses bounded write/drain operations. It does not raise a Rust-language panic. The ordinary Rust panic handler remains silent and stackless, preserving the pre-BSS validator's prohibition on consulting readiness globals. Unexpected Rust-panic serial reporting is not implemented by this change. Engineering lines are not the final M2 acceptance markers.

Panic-target Clippy with warnings denied passes. All four controlled cases stop at their exact expected PCs with SP inside the private stack budget. This is observed execution, not the pending static bound for all post-BSS console/panic paths.

## Unmodified and regression evidence

The [unmodified default run](evidence/p7-pi-console-controlled-unmodified.json) still rejects the zero-length measured-rate response at stage 4 with no serial bytes. No fallback was introduced. [Five entry-only regressions](evidence/p7-pi-console-controlled-entry.json) still pass with the separately recorded entry-only feature; their pre-BSS validator bound remains 21,440 bytes.

Next audit the full post-BSS console/deliberate-panic stack, test panic-reporting failures, finalize variant-specific acceptance diagnostics and integrate target packaging. Real firmware measured-tag support and physical Zero 2 W UART capture remain pending. M1, locked firmware and media are unchanged.
