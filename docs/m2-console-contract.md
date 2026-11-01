# M2 console contract proposal

2026-11-01. Console direction approved by the user. Not implemented or hardware verified. This closes the console direction discussion only; the complete P6 boot/image design remains open.

## Proposed behaviour

Use UART0/PL011 for transmit-only diagnostics at 115200 baud, eight data bits, no parity, one stop bit, no flow control. Select the Zero 2 W board explicitly. Keep Bluetooth unsupported during M2 and ensure its UART pins cannot compete with the diagnostic route. No interactive console or receive driver is required for startup/panic acceptance.

The Pi BSP owns GPIO routing, pull configuration, firmware clock interaction and initialization ordering. The reusable polling driver owns PL011 line configuration, byte transmission and final drain. The common kernel owns marker semantics. Only the primary core may initialize or use the console.

GPIO14 uses ALT0 for TXD0. For the first transmit-only test only that signal and common ground are needed; no Pi input is required. The board must be separately powered. Use an adapter verified to accept 3.3 V logic; do not connect its power lead. The final physical pin/wiring checklist waits for identification of the user's adapter and header.

The BCM2837 mapping translates the peripheral bus window to physical 0x3f000000. The candidate UART0 CPU address is 0x3f201000; GPIO is 0x3f200000. These are Pi BSP constants, never global replacements for the QEMU addresses. The BCM2835 manual supplies peripheral offsets and GPIO functions; its older CPU physical base must not be copied to this board.

## Clock and initialization requirements

Do not reuse QEMU's 24 MHz divisors. Request an explicit UART clock through the firmware property interface, validate the complete response and returned clock rate, and calculate divisors for the rate actually accepted. A requested 48 MHz clock gives IBRD=26 and FBRD=3 for 115200 baud; this is an arithmetic example, not proof of the physical clock. A missing, malformed, unsupported or timed-out clock response must prevent a success marker.

Mailbox code is a separate board service and needs bounded polling, correctly aligned and addressable buffers, ordered MMIO access, request/response correlation and strict length/status checks. Cache/MMU-off startup and buffer ownership must be established before its use. Exact mailbox transport and exception-level setup remain a prerequisite review; this proposal does not authorize guessing them.

Before routing TX, disable the UART and wait for prior transmission to settle. Configure GPIO/pulls, clock and UART divisors while disabled, clear/mask interrupts, set 8N1 and FIFO mode, enable transmit only, then emit diagnostics. All polling must terminate; a drain failure must prevent a pass. Review initialization ordering against both the manual and inherited firmware state during implementation.

## Two review methods

1. Hardware/firmware reference check: GPIO alternate-function table and UART register/divisor sections in the official peripheral manual; board address translation in the official BCM2837 device tree; property-interface clock request/response rules. The existing board device tree and disable-bt overlay independently show why Linux serial aliases are insufficient for our initialization.
2. Current-code and arithmetic check: the existing PL011 implementation already supports transmit-only 8N1/FIFO and bounded polling, but the HAL only carries base/divisors. Board preparation must precede constructing that driver, and any failure must reach the kernel without emitting startup success. Recompute the 48 MHz example as round(48,000,000 * 4 / 115,200)=1667 divisor units, split into 26 and 3. Output is approximately 115177 baud, about 0.02% error. No source or arithmetic check substitutes for captured hardware output.

## Acceptance checks

- Host tests cover divisor bounds/rounding and zero/invalid clocks; malformed and timed-out firmware replies must fail.
- Inspection checks GPIO routing and board-specific MMIO addresses, exclusive board selection and primary-core ownership.
- Existing QEMU startup/panic and failure-path regressions remain required after shared code changes.
- Physical test records the board, image hash, adapter/port and capture settings. Startup and deliberate panic use separate artifact identities and exact complete markers; unexpected faults, timeout or truncated output cannot pass.

## Sources

- [Official peripheral manual: GPIO alternate functions, UART chapter and memory ordering](https://datasheets.raspberrypi.com/bcm2835/bcm2835-peripherals.pdf)
- [BCM2837 address translation](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/broadcom/bcm2837.dtsi)
- [Firmware property interface](https://github.com/raspberrypi/firmware/wiki/Mailbox-property-interface)
- [Zero 2 W routing](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/broadcom/bcm2710-rpi-zero-2-w.dts)
- [GPIO electrical guidance](https://pip-assets.raspberrypi.com/categories/685-whitepapers-app-notes-compliance-guides/documents/RP-006553-WP/A-history-of-GPIO-usage-on-Raspberry-Pi-devices-and-current-best-practices)

Decision D15: user approved PL011 transmit-only diagnostics with BSP-owned clock/GPIO setup for M2 on 2026-11-01. This does not approve the still-open boot/image contracts or claim adapter availability.

## Approved final-token clarification

D23 is approved: bounded diagnostic and token-prefix drains precede the final LF. Host receipt of that LF establishes last-byte delivery; the kernel performs no subsequent fallible operation. See the [marker commit design](m2-marker-commit-review.md) and [implementation evidence](p7-marker-commit.md). This supersedes the earlier implied requirement for a separate BUSY-clear poll after the final token byte. Physical acceptance remains pending.
