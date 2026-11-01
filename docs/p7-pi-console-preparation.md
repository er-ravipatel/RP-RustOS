# P7 GPIO preparation and post-BSS console integration

2026-11-01. D22 default kernel path is now wired through GPIO preparation and real mailbox clock transactions. Successful serial initialization and full M2 startup/panic acceptance remain pending.

[Board preparation](../bsp/rpi-zero2w/src/uart_prepare.rs) boundedly drains inherited UART TX, disables UART/DMA/interrupts, confirms idle and then modifies only the owned diagnostic/Bluetooth UART pin fields. GPIO30-33 become inputs; GPIO14 is ALT0 TX and GPIO15 input. Other GPFSEL fields are preserved. The pull sequence uses two bounded 150 microsecond timer delays; a hold timeout releases the pull clock before returning an error.

The [default kernel](../bsp/rpi-zero2w/kernel/src/main.rs) calls preparation after full validation, BSS clearing and boot-record creation, then executes enable/set/measured clock operations using permanent buffers. Only a valid measured rate can construct/enable the reusable PL011 transmitter. Its initial engineering line is RUSTOS_PI_CONSOLE_READY followed by newline; it is not an M2 hardware acceptance marker. Every preparation/transmit/drain error enters an explicit debugger-visible failure park. Rust panic still parks silently; bounded panic serial diagnostics remain pending.

An explicit `entry-only` Cargo feature now halts at the pre-peripheral checkpoint for regression tests. Default builds do not enable that feature. The [entry runner](../tools/test_pi_kernel_entry.py) records its feature selection, so entry-only success is not represented as evidence that peripheral initialization succeeded.

## Actual default path result

The [default-path test](../tools/test_pi_console_path.py) builds and preserves a separate default ELF, starts four actual emulated cores behind the separate reset adapter, captures serial bytes and reads a bounded snapshot of the three clock buffers. [Observed QEMU evidence](evidence/p7-pi-console-path.json):

- Clock enable response is successful: UART ID 2, state 1, eight response bytes.
- Set-rate response is successful: UART ID 2, rate 48,000,000, eight response bytes.
- Measured-rate tag 0x00030047 returns a response-length field of 0x80000000 and zero rate. The required eight-byte measured response is absent.
- The kernel parks at console failure stage 4 with marker 0xc10c and no serial bytes. Other cores remain parked. There is no requested-rate fallback.

The test passing means the observed rejection is handled correctly. It does **not** mean QEMU UART output or physical firmware compatibility passed. The current QEMU model cannot establish the required measured-rate success path with this observed response.

## Verification and remaining scope

[51 BSP tests pass](evidence/p7-pi-console-preparation.json), including register-order/owned-field preservation, stuck UART, frozen timer and pull-clock release on hold timeout. Target Clippy with warnings denied passes. [Five explicit entry-only cases](evidence/p7-pi-console-entry-regression.json) pass multicore/BSS checks; their [pre-BSS stack bound](evidence/p7-pi-console-entry-stack.json) remains 21,440 bytes. That bound does not cover the new post-BSS console call path.

Next verify a controlled successful measured-rate path and UART transmit/drain failures, audit post-BSS console stack use, and implement bounded panic diagnostics and final variant-specific acceptance markers. Keep emulator limitations distinct from physical firmware testing. Image packaging and physical acceptance remain pending; no media was written and M1/locked firmware bytes remain unchanged.
