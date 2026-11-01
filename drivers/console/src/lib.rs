#![no_std]
use core::{
    fmt,
    ptr::{read_volatile, write_volatile},
};
use rustos_hal::{Console, ConsoleError};

/// Round the PL011 divisor to its nearest 1/64 step without accessing hardware.
/// The caller supplies the clock actually accepted by firmware, not a request.
/// None means zero inputs, baud above clock/16, or an unrepresentable divisor.
/// A representable divisor alone does not establish acceptable baud error.
pub fn baud_divisors(clock_hz: u32, baud: u32) -> Option<(u32, u32)> {
    if clock_hz == 0 || baud == 0 || u64::from(clock_hz) < 16 * u64::from(baud) {
        return None;
    }
    let units = (4 * u64::from(clock_hz) + u64::from(baud) / 2) / u64::from(baud);
    if !(64..=0x3f_ffff).contains(&units) {
        return None;
    }
    Some(((units / 64) as u32, (units % 64) as u32))
}

/// Exclusive polling PL011 access. No IRQ handlers, DMA or other core may use it.
pub struct Pl011 {
    base: usize,
}
impl Pl011 {
    /// # Safety
    /// base must identify a mapped PL011 with exclusive device ownership. Caller
    /// must configure the correct clock/baud divisor and retain valid MMIO access.
    pub unsafe fn new(base: usize) -> Self {
        Self { base }
    }
    fn read(&self, offset: usize) -> u32 {
        unsafe { read_volatile((self.base + offset) as *const u32) }
    }
    fn write(&self, offset: usize, value: u32) {
        unsafe { write_volatile((self.base + offset) as *mut u32, value) }
    }
    fn wait_clear(&self, mask: u32) -> Result<(), ConsoleError> {
        for _ in 0..1_000_000 {
            if self.read(0x18) & mask == 0 {
                return Ok(());
            }
            core::hint::spin_loop();
        }
        Err(ConsoleError::Timeout)
    }
    pub fn init(
        &mut self,
        integer_divisor: u32,
        fractional_divisor: u32,
    ) -> Result<(), ConsoleError> {
        self.wait_clear(1 << 3)?;
        self.write(0x30, 0); // Disable before changing line settings.
        self.write(0x38, 0); // No UART interrupts in M1.
        self.write(0x44, 0x7ff);
        self.write(0x24, integer_divisor);
        self.write(0x28, fractional_divisor);
        self.write(0x2c, (3 << 5) | (1 << 4)); // Eight bits, FIFO enabled.
        self.write(0x30, 1 | (1 << 8)); // UART + transmit only.
        Ok(())
    }
    fn byte(&mut self, byte: u8) -> Result<(), ConsoleError> {
        self.wait_clear(1 << 5)?;
        self.write(0, byte as u32);
        Ok(())
    }
}
impl fmt::Write for Pl011 {
    fn write_str(&mut self, value: &str) -> fmt::Result {
        for byte in value.bytes() {
            self.byte(byte).map_err(|_| fmt::Error)?;
        }
        Ok(())
    }
}
impl Console for Pl011 {
    fn flush(&mut self) -> Result<(), ConsoleError> {
        self.wait_clear(1 << 3)
    }
}

#[cfg(test)]
mod tests {
    use super::baud_divisors;

    #[test]
    fn known_qemu_and_pi_clock_examples() {
        assert_eq!(baud_divisors(24_000_000, 115_200), Some((13, 1)));
        assert_eq!(baud_divisors(48_000_000, 115_200), Some((26, 3)));
    }

    #[test]
    fn zero_or_impossible_rate_is_rejected() {
        assert_eq!(baud_divisors(0, 115_200), None);
        assert_eq!(baud_divisors(48_000_000, 0), None);
        assert_eq!(baud_divisors(48_000_000, 3_000_001), None);
        assert_eq!(baud_divisors(48_000_000, 3_000_000), Some((1, 0)));
    }

    #[test]
    fn divisor_register_limit_is_enforced() {
        assert_eq!(baud_divisors(16_777_212, 16), Some((65_535, 63)));
        assert_eq!(baud_divisors(16_777_216, 16), None);
    }

    #[test]
    fn large_clock_does_not_overflow_intermediate_arithmetic() {
        assert_eq!(baud_divisors(u32::MAX, 1_000_000), Some((268, 28)));
        assert_eq!(baud_divisors(u32::MAX, 1), None);
    }
}
