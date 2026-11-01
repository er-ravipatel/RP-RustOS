#![no_std]
use rustos_hal::ConsoleConfig;

/// QEMU virt's 24 MHz PL011, approximately 115200 baud; emulator profile only.
pub const CONSOLE: ConsoleConfig = ConsoleConfig {
    base: 0x0900_0000,
    integer_divisor: 13,
    fractional_divisor: 1,
};
