#![no_std]
#![no_main]
//! Pi-specific entry and initial console path; full M2 diagnostics are pending.
extern crate rustos_bsp_rpi_zero2w;
#[cfg(all(feature = "entry-only", feature = "panic-test"))]
compile_error!("entry-only and panic-test artifacts must be built separately");

// Reserved for the complete boot, including after a firmware timeout.
#[used]
#[no_mangle]
#[link_section = ".bss.pi_clock"]
static mut PI_CLOCK_BUFFERS: rustos_bsp_rpi_zero2w::uart_clock::ClockBuffers =
    rustos_bsp_rpi_zero2w::uart_clock::ClockBuffers::ZERO;

#[cfg(feature = "entry-only")]
core::arch::global_asm!(".equ PI_ENTRY_ONLY, 1");
core::arch::global_asm!(include_str!("entry.S"));
core::arch::global_asm!(include_str!("entry/cpu-guards.S"));
core::arch::global_asm!(include_str!("entry/preflight.S"));
core::arch::global_asm!(include_str!("entry/el1-transition.S"));
core::arch::global_asm!(include_str!("entry/finish.S"));

core::arch::global_asm!(
    ".section .text.console_parks,\"ax\"",
    ".global pi_console_failed",
    "pi_console_failed:",
    "wfe",
    "b pi_console_failed",
    ".global pi_console_ready",
    "pi_console_ready:",
    "wfe",
    "b pi_console_ready",
    ".global pi_deliberate_panic_park",
    "pi_deliberate_panic_park:",
    "wfe",
    "b pi_deliberate_panic_park",
    ".global pi_marker_commit_tail",
    ".type pi_marker_commit_tail,@function",
    "pi_marker_commit_tail:",
    "dsb sy",
    "mov x10, #0xc023",
    "b pi_marker_committed",
    ".size pi_marker_commit_tail, .-pi_marker_commit_tail",
    ".global pi_marker_committed",
    "pi_marker_committed:",
    "wfe",
    "b pi_marker_committed",
);

fn console_failure(stage: u64) -> ! {
    unsafe {
        core::arch::asm!("mov x10, #0xc10c", "mov x14, {stage}",
        "b pi_console_failed", stage=in(reg)stage, options(noreturn))
    }
}

/// Entry reaches this only after full memory validation, BSS clear and boot record.
///
/// # Safety
/// Caller must establish the Pi entry CPU/memory contract, exclusive primary-core
/// device ownership and initialized permanent BSS, and call this only once.
#[no_mangle]
pub unsafe extern "C" fn pi_initialize_console() -> ! {
    use core::fmt::Write;
    use rustos_bsp_rpi_zero2w::{
        uart_clock::{PiRegisters, UartClock},
        uart_prepare,
    };
    use rustos_hal::Console;
    extern "C" {
        static __bss_start: u8;
        static __bss_end: u8;
    }
    // SAFETY: the Pi entry proves single-core EL1, masked IRQs and MMU/caches off.
    let mut registers = unsafe { PiRegisters::new() };
    if uart_prepare::quiesce(&mut registers).is_err() {
        console_failure(1);
    }
    if uart_prepare::route_tx(&mut registers).is_err() {
        console_failure(2);
    }
    let rate = {
        // SAFETY: retained dedicated BSS storage, never referenced or reclaimed.
        let mut clock = unsafe {
            UartClock::new(
                &mut registers,
                core::ptr::addr_of_mut!(PI_CLOCK_BUFFERS),
                core::ptr::addr_of!(__bss_start) as u64,
                core::ptr::addr_of!(__bss_end) as u64,
            )
        }
        .unwrap_or_else(|_| console_failure(3));
        clock.configure().unwrap_or_else(|_| console_failure(4))
    };
    // SAFETY: exclusive primary-core PL011, board pins/clock prepared above.
    let mut uart = unsafe { rustos_console::Pl011::new(uart_prepare::UART_BASE) };
    if uart.init(rate.integer, rate.fractional).is_err() {
        console_failure(5);
    }
    // Engineering diagnostic only; not the M2 hardware-acceptance pass marker.
    if uart.write_str("RUSTOS_PI_CONSOLE_READY\n").is_err() {
        console_failure(6);
    }
    if uart.flush().is_err() {
        console_failure(7);
    }
    #[cfg(feature = "panic-test")]
    deliberate_panic(&mut uart);
    #[cfg(not(feature = "panic-test"))]
    commit_marker(&mut uart, "RUSTOS_BOOT_OK");
}

/// Explicit ready-console capability avoids reading global state in early panic.
#[cfg(feature = "panic-test")]
fn deliberate_panic(uart: &mut rustos_console::Pl011) -> ! {
    use core::fmt::Write;
    use rustos_hal::Console;
    if uart.write_str("RUSTOS_PI_DELIBERATE_PANIC\n").is_err() {
        console_failure(8);
    }
    if uart.flush().is_err() {
        console_failure(9);
    }
    commit_marker(uart, "RUSTOS_EXPECTED_PANIC");
}

/// D23: every software drain precedes LF. Host receipt proves final-byte delivery.
#[inline(never)]
fn commit_marker(uart: &mut rustos_console::Pl011, prefix: &str) -> ! {
    use core::fmt::Write;
    use rustos_hal::Console;
    if uart.write_str(prefix).is_err() {
        console_failure(10);
    }
    if uart.flush().is_err() {
        console_failure(11);
    }
    if uart.write_str("\n").is_err() {
        console_failure(12);
    }
    // No later fallible operation or status poll may invalidate this commit.
    unsafe { core::arch::asm!("b pi_marker_commit_tail", options(noreturn)) }
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    unsafe { core::arch::asm!("b pi_panic_park", options(noreturn)) }
}
