# P7 first implementation slice: portable UART divisors

2026-11-01. P7 has started with host-testable console preparation. The Pi startup, GPIO, mailbox and assembler backend are not implemented by this change.

Added [baud_divisors](../drivers/console/src/lib.rs), a pure no_std calculation using the firmware-accepted clock rate. It rounds the PL011 divisor to the nearest 1/64 step, rejects zero/impossible baud rates and register overflow, and uses wide intermediates for large clocks. It does not access MMIO or promise that every representable divisor has acceptable baud error. The future board layer must validate the actual clock and required output rate before using it.

Validation: four host unit tests pass for known 24/48 MHz examples, zero/above-maximum rates, register boundaries and large intermediate values. The console crate passes the AArch64 no_std check and workspace formatting check. The existing [five-scenario QEMU regression](evidence/p7-console-m1-regression.json) passes: startup, deliberate panic, injected exception, unexpected panic and unsupported entry. This is development-harness evidence, not a new production bundle or Pi hardware result. Existing M1 published output is unchanged.

## Queue reconciliation

D15–D19 establish the approved host-design and asset baseline. P6 remains open because hardware inventory and final handoff details are incomplete; it now occupies the supporting research/handoff slot. P7 occupies the single primary slot. This keeps the agreed maximum of two active items within M2 and allows host implementation without pretending the hardware setup is ready. P8/P9 remain queued.

P6's original hardware-inventory exit condition has not been marked satisfied or removed. No requirements or hardware acceptance stages are completed by this queue adjustment. Exact startup/register implementation review remains part of P7 before executing new board code.

Next P7 slice: explicit target/board selection and typed Pi profile loading, followed by board initialization. Preserve strict M1 compatibility and unsupported-target rejection until the Pi backend is actually ready.
