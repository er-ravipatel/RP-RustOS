#![no_std]
#![no_main]
use core::{
    arch::{asm, global_asm},
    fmt::Write,
    panic::PanicInfo,
    ptr::{addr_of, read_volatile},
    sync::atomic::{AtomicBool, Ordering},
};
use rustos_bsp_qemu_virt as board;
use rustos_hal::Console;

#[cfg(not(target_arch = "aarch64"))]
compile_error!("Build with --target aarch64-unknown-none-softfloat");
#[cfg(any(
    all(feature = "panic-test", feature = "fault-test"),
    all(feature = "panic-test", feature = "unexpected-panic-test"),
    all(feature = "fault-test", feature = "unexpected-panic-test")
))]
compile_error!("Select at most one internal test variant");
global_asm!(include_str!("entry.S"));

#[used]
#[no_mangle]
static mut BSS_SENTINEL: u64 = 0;
#[used]
static mut DATA_SENTINEL: u64 = 0x5255_5354_4f53_0001;
static EXPECTED_PANIC: AtomicBool = AtomicBool::new(false);

fn halt() -> ! {
    loop {
        unsafe {
            asm!("wfe", options(nomem, nostack));
        }
    }
}
fn console() -> rustos_console::Pl011 {
    // One CPU, masked interrupts; a fatal handler never resumes its caller.
    let mut uart = unsafe { rustos_console::Pl011::new(board::CONSOLE.base) };
    if uart
        .init(
            board::CONSOLE.integer_divisor,
            board::CONSOLE.fractional_divisor,
        )
        .is_err()
    {
        halt();
    }
    uart
}
fn emit(uart: &mut rustos_console::Pl011, arguments: core::fmt::Arguments<'_>) {
    if uart.write_fmt(arguments).is_err() || uart.flush().is_err() {
        halt();
    }
}

#[no_mangle]
pub extern "C" fn kernel_main() -> ! {
    let mut uart = console();
    let (sp, el, sctlr, vbar): (u64, u64, u64, u64);
    unsafe {
        asm!("mov {0}, sp", "mrs {1}, CurrentEL", "mrs {2}, sctlr_el1", "mrs {3}, vbar_el1", out(reg) sp, out(reg) el, out(reg) sctlr, out(reg) vbar, options(nomem, nostack));
    }
    let (bss, data) = unsafe {
        (
            read_volatile(addr_of!(BSS_SENTINEL)),
            read_volatile(addr_of!(DATA_SENTINEL)),
        )
    };
    extern "C" {
        static __stack_bottom: u8;
        static __stack_top: u8;
        static vectors: u8;
    }
    let (bottom, top, expected_vectors) = (
        addr_of!(__stack_bottom) as u64,
        addr_of!(__stack_top) as u64,
        addr_of!(vectors) as u64,
    );
    if sp & 15 != 0
        || sp < bottom
        || sp >= top
        || el != 4
        || sctlr & 0x1005 != 0
        || vbar & 2047 != 0
        || vbar != expected_vectors
        || bss != 0
        || data != 0x5255_5354_4f53_0001
    {
        panic!("startup invariant failed");
    }
    emit(
        &mut uart,
        format_args!(
            "RustOS M1: EL1 stack=aligned BSS=zero data=ok vectors=aligned MMU/cache=off\n"
        ),
    );
    #[cfg(feature = "fault-test")]
    unsafe {
        asm!("brk #0", options(nomem, nostack));
    }
    #[cfg(feature = "unexpected-panic-test")]
    panic!("P4 unexpected panic injection");
    #[cfg(feature = "panic-test")]
    {
        EXPECTED_PANIC.store(true, Ordering::SeqCst);
        panic!("P4 deliberate panic");
    }
    #[cfg(not(any(feature = "panic-test", feature = "unexpected-panic-test")))]
    {
        emit(&mut uart, format_args!("RUSTOS_BOOT_OK\n"));
        halt();
    }
}

#[panic_handler]
fn panic(info: &PanicInfo<'_>) -> ! {
    let mut uart = console();
    let expected = EXPECTED_PANIC.swap(false, Ordering::SeqCst)
        && info.message().as_str() == Some("P4 deliberate panic");
    emit(&mut uart, format_args!("panic: {}\n", info));
    emit(
        &mut uart,
        format_args!(
            "{}\n",
            if expected {
                "RUSTOS_EXPECTED_PANIC"
            } else {
                "RUSTOS_UNEXPECTED_PANIC"
            }
        ),
    );
    halt();
}

#[no_mangle]
pub extern "C" fn kernel_exception(esr: u64, elr: u64, far: u64) -> ! {
    let mut uart = console();
    emit(
        &mut uart,
        format_args!(
            "RUSTOS_EXCEPTION ESR={:#x} ELR={:#x} FAR={:#x}\n",
            esr, elr, far
        ),
    );
    halt();
}
