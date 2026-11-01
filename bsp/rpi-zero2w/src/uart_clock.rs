//! D22 hardware boundary. Call only after proven RAM, BSS clear and UART idle.
use crate::mailbox::{property_word, ClockOperation, ClockSlots, MailboxError, MailboxIo};
use core::{marker::PhantomData, ptr};

pub const MAILBOX_BASE: usize = 0x3f00_b880;
pub const TIMER_CLO: usize = 0x3f00_3004;

/// Must be permanently reserved in kernel BSS, never stack or reclaimable memory.
#[repr(C, align(64))]
pub struct ClockBuffers {
    words: [[u32; 16]; 3],
}

impl ClockBuffers {
    pub const ZERO: Self = Self {
        words: [[0; 16]; 3],
    };
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UartRate {
    pub measured_hz: u32,
    pub integer: u32,
    pub fractional: u32,
}

impl UartRate {
    pub fn from_measured(measured_hz: u32) -> Result<Self, MailboxError> {
        let (integer, fractional) =
            rustos_console::baud_divisors(measured_hz, 115_200).ok_or(MailboxError::Clock)?;
        let wanted = 115_200u64 * (u64::from(integer) * 64 + u64::from(fractional));
        let numerator = u64::from(measured_hz) * 4;
        if numerator.abs_diff(wanted) * 100 > wanted {
            return Err(MailboxError::Clock);
        }
        Ok(Self {
            measured_hz,
            integer,
            fractional,
        })
    }
}

/// Mockable register boundary; hardware ownership is established by its owner.
pub trait Registers {
    fn read(&mut self, address: usize) -> u32;
    fn write(&mut self, address: usize, value: u32);
    fn barrier(&mut self);
}

impl<R: Registers> Registers for &mut R {
    fn read(&mut self, address: usize) -> u32 {
        (**self).read(address)
    }
    fn write(&mut self, address: usize, value: u32) {
        (**self).write(address, value);
    }
    fn barrier(&mut self) {
        (**self).barrier();
    }
}

/// Exclusive primary-core service. No reset/clone/release or buffer references.
pub struct UartClock<R> {
    registers: R,
    buffers: *mut ClockBuffers,
    bss_start: u64,
    bss_end: u64,
    slots: ClockSlots,
    attempted: bool,
    // Do not move device ownership to another core/thread or share it.
    _exclusive: PhantomData<*mut ()>,
}

impl<R: Registers> UartClock<R> {
    /// # Safety
    /// `buffers` must point to one initialized, lifetime-long, exclusively owned
    /// ClockBuffers allocation at its numeric physical address in the proven BSS.
    /// No references/other owners may access it, including after this owner drops
    /// or firmware times out. Call exactly once per boot with a unique allocation.
    /// MMU/caches must be off, DAIF masked, primary core at EL1; UART must already
    /// be disabled/idle. Registers must exclusively own the mapped board devices.
    pub unsafe fn new(
        registers: R,
        buffers: *mut ClockBuffers,
        bss_start: u64,
        bss_end: u64,
    ) -> Result<Self, MailboxError> {
        let base = buffers as u64;
        for offset in [0, 64, 128] {
            property_word(
                base.checked_add(offset).ok_or(MailboxError::Address)?,
                bss_start,
                bss_end,
            )?;
        }
        Ok(Self {
            registers,
            buffers,
            bss_start,
            bss_end,
            slots: ClockSlots::default(),
            attempted: false,
            _exclusive: PhantomData,
        })
    }

    pub fn configure(&mut self) -> Result<UartRate, MailboxError> {
        if self.attempted {
            return Err(MailboxError::AlreadyUsed);
        }
        self.attempted = true;
        self.registers.barrier();
        let result = configure_sequence(|index, operation| {
            // SAFETY: constructor proves the complete three-buffer allocation;
            // each operation gets a distinct slot with lifetime-long storage.
            let buffer = unsafe { self.buffers.cast::<u32>().add(index * 16) };
            let mut port = Port {
                registers: &mut self.registers,
                buffer,
            };
            self.slots.exchange(
                &mut port,
                operation,
                buffer as u64,
                self.bss_start,
                self.bss_end,
            )
        });
        self.registers.barrier();
        if result.is_err() {
            self.slots.poison();
        }
        result
    }
}

fn configure_sequence(
    mut exchange: impl FnMut(usize, ClockOperation) -> Result<u32, MailboxError>,
) -> Result<UartRate, MailboxError> {
    exchange(0, ClockOperation::Enable)?;
    exchange(1, ClockOperation::SetRate)?;
    UartRate::from_measured(exchange(2, ClockOperation::MeasuredRate)?)
}

struct Port<'a, R> {
    registers: &'a mut R,
    buffer: *mut u32,
}

impl<R: Registers> MailboxIo for Port<'_, R> {
    fn now_us(&mut self) -> u32 {
        self.registers.read(TIMER_CLO)
    }
    fn rx_status(&mut self) -> u32 {
        self.registers.read(MAILBOX_BASE + 0x18)
    }
    fn tx_status(&mut self) -> u32 {
        self.registers.read(MAILBOX_BASE + 0x38)
    }
    fn receive(&mut self) -> u32 {
        self.registers.read(MAILBOX_BASE)
    }
    fn submit(&mut self, word: u32) {
        self.registers.write(MAILBOX_BASE + 0x20, word);
    }
    fn barrier(&mut self) {
        self.registers.barrier();
    }
    fn buffer_write(&mut self, index: usize, value: u32) {
        assert!(index < 16);
        // SAFETY: private Port is bound to the unique validated slot; the
        // transport writes only before submitting ownership to firmware.
        unsafe { ptr::write_volatile(self.buffer.add(index), value) };
    }
    fn buffer_read(&mut self, index: usize) -> u32 {
        assert!(index < 16);
        // SAFETY: transport reads only after correlated completion + barrier.
        unsafe { ptr::read_volatile(self.buffer.add(index)) }
    }
}

#[cfg(target_arch = "aarch64")]
pub struct PiRegisters {
    _private: (),
}

#[cfg(target_arch = "aarch64")]
impl PiRegisters {
    /// # Safety
    /// Caller exclusively owns the mapped Zero 2 W mailbox/timer devices, with
    /// valid EL1 access, caches/MMU off and no concurrent device clients.
    pub unsafe fn new() -> Self {
        Self { _private: () }
    }
}

#[cfg(target_arch = "aarch64")]
impl Registers for PiRegisters {
    fn read(&mut self, address: usize) -> u32 {
        assert!(
            matches!(address, TIMER_CLO | MAILBOX_BASE)
                || address == MAILBOX_BASE + 0x18
                || address == MAILBOX_BASE + 0x38
                || address == crate::uart_prepare::UART_BASE + 0x18
                || address == crate::uart_prepare::GPIO_BASE + 4
                || address == crate::uart_prepare::GPIO_BASE + 12
        );
        unsafe { ptr::read_volatile(address as *const u32) }
    }
    fn write(&mut self, address: usize, value: u32) {
        assert!(
            address == MAILBOX_BASE + 0x20
                || [0x30, 0x48, 0x38, 0x44]
                    .iter()
                    .any(|offset| address == crate::uart_prepare::UART_BASE + offset)
                || [4, 12, 0x94, 0x98]
                    .iter()
                    .any(|offset| address == crate::uart_prepare::GPIO_BASE + offset)
        );
        unsafe { ptr::write_volatile(address as *mut u32, value) };
    }
    fn barrier(&mut self) {
        unsafe { core::arch::asm!("dsb sy", options(nostack, preserves_flags)) };
    }
}

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;
    use std::vec::Vec;

    #[test]
    fn measured_rate_controls_divisors_and_bounds() {
        assert_eq!(UartRate::from_measured(48_000_000).unwrap().integer, 26);
        let rate = UartRate::from_measured(24_000_000).unwrap();
        assert_eq!((rate.integer, rate.fractional), (13, 1));
        for rate in [0, 1, 1_843_199] {
            assert_eq!(UartRate::from_measured(rate), Err(MailboxError::Clock));
        }
    }

    struct Trace {
        reads: Vec<usize>,
        writes: Vec<(usize, u32)>,
        barriers: usize,
    }

    #[test]
    fn clock_sequence_uses_measured_rate_and_stops_at_first_failure() {
        let mut calls = Vec::new();
        let rate = configure_sequence(|index, operation| {
            calls.push((index, operation));
            Ok(match operation {
                ClockOperation::Enable => 1,
                ClockOperation::SetRate => 48_000_000,
                ClockOperation::MeasuredRate => 24_000_000,
            })
        })
        .unwrap();
        assert_eq!(
            calls,
            [
                (0, ClockOperation::Enable),
                (1, ClockOperation::SetRate),
                (2, ClockOperation::MeasuredRate)
            ]
        );
        assert_eq!(
            (rate.measured_hz, rate.integer, rate.fractional),
            (24_000_000, 13, 1)
        );
        for failure in 0..3 {
            let mut count = 0;
            assert_eq!(
                configure_sequence(|index, _| {
                    count += 1;
                    if index == failure {
                        Err(MailboxError::Timeout)
                    } else {
                        Ok(1)
                    }
                }),
                Err(MailboxError::Timeout)
            );
            assert_eq!(count, failure + 1);
        }
    }
    impl Registers for Trace {
        fn read(&mut self, address: usize) -> u32 {
            self.reads.push(address);
            123
        }
        fn write(&mut self, address: usize, value: u32) {
            self.writes.push((address, value));
        }
        fn barrier(&mut self) {
            self.barriers += 1;
        }
    }

    #[test]
    fn volatile_port_uses_exact_registers_and_slot() {
        let mut buffers = ClockBuffers::ZERO;
        assert_eq!(
            (
                core::mem::size_of::<ClockBuffers>(),
                core::mem::align_of::<ClockBuffers>()
            ),
            (192, 64)
        );
        let mut trace = Trace {
            reads: Vec::new(),
            writes: Vec::new(),
            barriers: 0,
        };
        let buffer = buffers.words[1].as_mut_ptr();
        let mut port = Port {
            registers: &mut trace,
            buffer,
        };
        port.buffer_write(15, 42);
        assert_eq!(port.buffer_read(15), 42);
        port.now_us();
        port.rx_status();
        port.tx_status();
        port.receive();
        port.submit(0xc0210048);
        port.barrier();
        assert_eq!(
            trace.reads,
            [
                TIMER_CLO,
                MAILBOX_BASE + 0x18,
                MAILBOX_BASE + 0x38,
                MAILBOX_BASE
            ]
        );
        assert_eq!(trace.writes, [(MAILBOX_BASE + 0x20, 0xc0210048)]);
        assert_eq!(trace.barriers, 1);
        assert_eq!(buffers.words[0], [0; 16]);
        assert_eq!(buffers.words[2], [0; 16]);
    }
}
