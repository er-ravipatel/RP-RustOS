# P7 permanent mailbox buffers and UART clock backend

2026-11-01. D22 implementation continues. [Backend source](../bsp/rpi-zero2w/src/uart_clock.rs), [verification record](evidence/p7-uart-clock-backend.json).

Added a 192-byte, 64-byte aligned ClockBuffers type and a retained lifetime-long kernel BSS allocation with three distinct slots. The linker keeps that section even before a caller is wired. The unsafe primary-core owner validates all three complete buffer extents against the proven BSS/kernel reservation and requires exclusive raw-pointer ownership for the entire boot, including after timeout/drop. It exposes no references, reset or retry; a second configure attempt is rejected. Hardware construction remains unsafe because no local check can prove lifetime-long ownership or CPU/device exclusivity.

The volatile port accesses the reviewed mailbox receive/status/transmit offsets and system timer. The AArch64 register backend uses 32-bit volatile operations and DSB SY. Buffer reads/writes use raw volatile pointers; references to the firmware allocation are not retained during a transaction. Enable, set-rate and measured-rate operations use distinct slots, with no fallback or later exchange after failure.

The baud result uses the shared console divisor helper plus the approved 1% error bound. A mock sequence explicitly requests 48 MHz but returns 24 MHz measured; divisors become 13/1, proving the requested rate is not substituted for the measured value. Failures at each of the three stages prevent subsequent queries. An initial test incorrectly expected u32::MAX Hz to be unrepresentable; arithmetic showed its divisor still fits, so that incorrect expectation was removed without narrowing the runtime contract.

Validation passes: 48 BSP tests, four shared console helper tests, host BSP Clippy and Pi-target Clippy with warnings denied, and release AArch64 build. The volatile-port trace test confirms exact mailbox/timer addresses and that modifying the middle slot leaves the other two unchanged.

[Five actual Pi entry cases](evidence/p7-uart-clock-entry.json) pass with the buffers retained, including BSS sentinel/write-order checks and all four emulated cores. The runner checks the actual buffer symbol's 64-byte alignment and full 192-byte BSS containment. The [pre-BSS validator stack](evidence/p7-uart-clock-stack.json) remains bounded at 21,440 bytes.

The clock backend is compiled and reviewed but is **not yet called by the kernel**. These results do not establish property-tag support, observed UART clock behavior or the future console path stack bound. Next implement GPIO/PL011 disable/idle/routing/pull setup and connect this backend after BSS; then test firmware responses and startup/panic diagnostics. No physical Pi, serial output, packaged image or media operation is claimed. M1 sources and the approved asset lock remain unchanged.
